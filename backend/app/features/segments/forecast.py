from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.learning.models import ActionFeatureSnapshot, OutcomeEvent
from app.features.segments.models import AudienceSegment, AudienceSegmentMember
from app.features.segments.schemas import SegmentCriteria


READINESS_BUCKET_SIZE = 20
MAX_HISTORY = 50_000
EVENT_QUERY_CHUNK = 4_000
EXACT_MIN_SAMPLES = 20
MARGINAL_MIN_SAMPLES = 40
STRATUM_PRIOR_STRENGTH = 20.0


class SegmentYieldForecastService:
    """Estimate observational downstream yield with explicit uncertainty.

    This is intentionally not an incremental/causal estimate. It answers
    "what outcome rate has historically followed actions on people like this?"
    using only mature action cohorts and partial pooling for sparse strata.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def forecast(
        self,
        *,
        owner_id: UUID,
        segment_id: UUID,
        stage: str = "business",
        event_type: str = "converted",
        horizon_hours: int = 168,
        budget: int = 1_000,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        normalized_stage = stage.strip().lower()
        normalized_type = event_type.strip().lower().replace(" ", "_")
        if normalized_stage not in {"engagement", "business"}:
            raise ValueError("Expected Yield supports engagement or business outcomes only")
        if not normalized_type:
            raise ValueError("event_type is required")
        if horizon_hours < 1 or horizon_hours > 2160:
            raise ValueError("horizon_hours must be between 1 and 2160")
        if budget < 1 or budget > 50_000:
            raise ValueError("budget must be between 1 and 50000")
        if min_confidence < 0 or min_confidence > 1:
            raise ValueError("min_confidence must be between 0 and 1")

        segment_result = await self.session.execute(
            select(AudienceSegment).where(
                AudienceSegment.id == segment_id,
                AudienceSegment.owner_id == owner_id,
            )
        )
        segment = segment_result.scalar_one_or_none()
        if segment is None:
            raise ValueError("Opportunity not found")
        if not segment.is_active:
            raise ValueError("Archived Opportunity cannot be forecast")
        if segment.last_refreshed_at is None:
            raise ValueError("Opportunity must be materialized before forecasting")

        criteria = SegmentCriteria.model_validate(segment.criteria)
        members = await self._current_members(segment.id, criteria, budget)
        if not members:
            return self._empty(
                segment=segment,
                stage=normalized_stage,
                event_type=normalized_type,
                horizon_hours=horizon_hours,
                budget=budget,
                warnings=["empty_opportunity", "observational_not_causal"],
            )

        history, history_capped = await self._mature_history(
            owner_id=owner_id,
            platform=segment.platform,
            horizon_hours=horizon_hours,
        )
        if not history:
            return self._empty(
                segment=segment,
                stage=normalized_stage,
                event_type=normalized_type,
                horizon_hours=horizon_hours,
                budget=budget,
                evaluated_members=len(members),
                warnings=["no_mature_history", "observational_not_causal"],
            )

        positives = await self._positive_jobs(
            history=history,
            owner_id=owner_id,
            stage=normalized_stage,
            event_type=normalized_type,
            horizon_hours=horizon_hours,
            min_confidence=min_confidence,
        )

        global_samples = len(history)
        global_positives = len(positives)
        global_alpha = global_positives + 0.5
        global_beta = global_samples - global_positives + 0.5
        global_mean = global_alpha / (global_alpha + global_beta)

        exact_stats: dict[tuple[int, str], Counter[str]] = defaultdict(Counter)
        readiness_stats: dict[int, Counter[str]] = defaultdict(Counter)
        signal_stats: dict[str, Counter[str]] = defaultdict(Counter)
        frozen_history = 0

        for snapshot in history:
            readiness_bucket = self._readiness_bucket(snapshot.readiness_score)
            signal = snapshot.strongest_signal_type or "no_intent_signal"
            positive = snapshot.action_job_id in positives
            self._add_stat(exact_stats[(readiness_bucket, signal)], positive)
            self._add_stat(readiness_stats[readiness_bucket], positive)
            self._add_stat(signal_stats[signal], positive)
            if (snapshot.feature_payload or {}).get("decision_source") == "frozen_campaign_cohort":
                frozen_history += 1

        group_counts: Counter[tuple[str, str]] = Counter()
        group_posteriors: dict[tuple[str, str], tuple[float, float, Counter[str], str]] = {}
        coverage = Counter()

        for member in members:
            bucket = self._readiness_bucket(member.readiness_score)
            signal = member.strongest_signal_type or "no_intent_signal"
            exact = exact_stats[(bucket, signal)]
            readiness = readiness_stats[bucket]
            signal_only = signal_stats[signal]

            if exact["samples"] >= EXACT_MIN_SAMPLES:
                level = "exact"
                label = f"{self._bucket_label(bucket)} · {signal}"
                stats = exact
                key = (level, f"{bucket}:{signal}")
            elif readiness["samples"] >= MARGINAL_MIN_SAMPLES:
                level = "readiness"
                label = self._bucket_label(bucket)
                stats = readiness
                key = (level, str(bucket))
            elif signal_only["samples"] >= MARGINAL_MIN_SAMPLES:
                level = "signal"
                label = signal
                stats = signal_only
                key = (level, signal)
            else:
                level = "global"
                label = "owner baseline"
                stats = Counter(samples=global_samples, positives=global_positives)
                key = (level, "global")

            if key not in group_posteriors:
                if level == "global":
                    alpha, beta = global_alpha, global_beta
                else:
                    alpha = stats["positives"] + global_mean * STRATUM_PRIOR_STRENGTH
                    beta = (
                        stats["samples"] - stats["positives"]
                        + (1.0 - global_mean) * STRATUM_PRIOR_STRENGTH
                    )
                group_posteriors[key] = (alpha, beta, stats, label)
            group_counts[key] += 1
            coverage[level] += 1

        expected = 0.0
        variance = 0.0
        evidence_rows: list[dict[str, Any]] = []
        for key, count in group_counts.items():
            level = key[0]
            alpha, beta, stats, label = group_posteriors[key]
            posterior_rate, low, high = self._beta_summary(alpha, beta)
            expected += count * posterior_rate
            variance += self._beta_binomial_variance(count, alpha, beta)
            observed_rate = stats["positives"] / stats["samples"] if stats["samples"] else 0.0
            evidence_rows.append(
                {
                    "label": label,
                    "evidence_level": level,
                    "current_members": count,
                    "historical_samples": int(stats["samples"]),
                    "historical_positives": int(stats["positives"]),
                    "observed_rate": round(observed_rate * 100.0, 2),
                    "posterior_rate": round(posterior_rate * 100.0, 2),
                    "confidence_low": round(low * 100.0, 2),
                    "confidence_high": round(high * 100.0, 2),
                }
            )

        evaluated = len(members)
        sd = math.sqrt(max(variance, 0.0))
        low_outcomes = max(0.0, expected - 1.96 * sd)
        high_outcomes = min(float(evaluated), expected + 1.96 * sd)
        coverage_pct = {
            level: round(coverage[level] / evaluated * 100.0, 2)
            for level in ("exact", "readiness", "signal", "global")
        }
        non_global = 1.0 - coverage["global"] / evaluated
        frozen_ratio = frozen_history / global_samples if global_samples else 0.0

        warnings = ["observational_not_causal"]
        if history_capped:
            warnings.append("history_capped")
        if frozen_ratio < 0.7:
            warnings.append("legacy_decision_snapshot_mix")
        if non_global < 0.7:
            warnings.append("low_contextual_evidence_coverage")
        if global_samples < 100:
            warnings.append("small_mature_history")

        if global_samples < 30:
            quality = "insufficient"
        elif global_samples >= 100 and non_global >= 0.7 and frozen_ratio >= 0.7:
            quality = "ready"
        else:
            quality = "limited"

        evidence_rows.sort(
            key=lambda row: (row["current_members"], row["historical_samples"]),
            reverse=True,
        )
        return {
            "segment_id": segment.id,
            "segment_name": segment.name,
            "platform": segment.platform,
            "stage": normalized_stage,
            "event_type": normalized_type,
            "horizon_hours": horizon_hours,
            "requested_budget": budget,
            "evaluated_members": evaluated,
            "historical_samples": global_samples,
            "historical_positives": global_positives,
            "historical_observed_rate": round(global_positives / global_samples * 100.0, 2),
            "expected_outcomes": round(expected, 2),
            "expected_rate": round(expected / evaluated * 100.0, 2),
            "confidence_low_outcomes": round(low_outcomes, 2),
            "confidence_high_outcomes": round(high_outcomes, 2),
            "confidence_low_rate": round(low_outcomes / evaluated * 100.0, 2),
            "confidence_high_rate": round(high_outcomes / evaluated * 100.0, 2),
            "frozen_history_ratio": round(frozen_ratio * 100.0, 2),
            "evidence_coverage": coverage_pct,
            "quality_status": quality,
            "warnings": warnings,
            "evidence_rows": evidence_rows[:20],
        }

    async def _current_members(
        self,
        segment_id: UUID,
        criteria: SegmentCriteria,
        budget: int,
    ) -> list[AudienceSegmentMember]:
        if criteria.sort_by == "intent":
            ordering = (
                AudienceSegmentMember.intent_score.desc().nullslast(),
                AudienceSegmentMember.readiness_score.desc().nullslast(),
                AudienceSegmentMember.activity_score.desc().nullslast(),
            )
        elif criteria.sort_by == "activity":
            ordering = (
                AudienceSegmentMember.activity_score.desc().nullslast(),
                AudienceSegmentMember.readiness_score.desc().nullslast(),
                AudienceSegmentMember.intent_score.desc().nullslast(),
            )
        else:
            ordering = (
                AudienceSegmentMember.readiness_score.desc().nullslast(),
                AudienceSegmentMember.intent_score.desc().nullslast(),
                AudienceSegmentMember.activity_score.desc().nullslast(),
            )
        result = await self.session.execute(
            select(AudienceSegmentMember)
            .where(AudienceSegmentMember.segment_id == segment_id)
            .order_by(*ordering)
            .limit(budget)
        )
        return list(result.scalars().all())

    async def _mature_history(
        self,
        *,
        owner_id: UUID,
        platform: str,
        horizon_hours: int,
    ) -> tuple[list[ActionFeatureSnapshot], bool]:
        mature_cutoff = datetime.now(timezone.utc) - timedelta(hours=horizon_hours)
        result = await self.session.execute(
            select(ActionFeatureSnapshot)
            .where(
                ActionFeatureSnapshot.owner_id == owner_id,
                ActionFeatureSnapshot.platform == platform,
                ActionFeatureSnapshot.first_transport_at.is_not(None),
                ActionFeatureSnapshot.first_transport_at <= mature_cutoff,
                ActionFeatureSnapshot.readiness_score.is_not(None),
            )
            .order_by(ActionFeatureSnapshot.first_transport_at.desc())
            .limit(MAX_HISTORY + 1)
        )
        items = list(result.scalars().all())
        return items[:MAX_HISTORY], len(items) > MAX_HISTORY

    async def _positive_jobs(
        self,
        *,
        history: list[ActionFeatureSnapshot],
        owner_id: UUID,
        stage: str,
        event_type: str,
        horizon_hours: int,
        min_confidence: float,
    ) -> set[UUID]:
        snapshot_by_job = {snapshot.action_job_id: snapshot for snapshot in history}
        job_ids = list(snapshot_by_job)
        positives: set[UUID] = set()
        horizon = timedelta(hours=horizon_hours)
        for start in range(0, len(job_ids), EVENT_QUERY_CHUNK):
            chunk = job_ids[start : start + EVENT_QUERY_CHUNK]
            result = await self.session.execute(
                select(OutcomeEvent).where(
                    OutcomeEvent.owner_id == owner_id,
                    OutcomeEvent.action_job_id.in_(chunk),
                    OutcomeEvent.stage == stage,
                    OutcomeEvent.event_type == event_type,
                    OutcomeEvent.success.is_(True),
                    OutcomeEvent.confidence >= min_confidence,
                )
            )
            for event in result.scalars().all():
                if event.action_job_id is None:
                    continue
                snapshot = snapshot_by_job.get(event.action_job_id)
                if snapshot is None or snapshot.first_transport_at is None:
                    continue
                start_at = self._aware(snapshot.first_transport_at)
                observed_at = self._aware(event.observed_at)
                if start_at <= observed_at <= start_at + horizon:
                    positives.add(event.action_job_id)
        return positives

    @staticmethod
    def _add_stat(counter: Counter[str], positive: bool) -> None:
        counter["samples"] += 1
        if positive:
            counter["positives"] += 1

    @staticmethod
    def _readiness_bucket(value: float | None) -> int:
        score = max(0.0, min(float(value or 0.0), 100.0))
        return min(int(score // READINESS_BUCKET_SIZE) * READINESS_BUCKET_SIZE, 80)

    @staticmethod
    def _bucket_label(start: int) -> str:
        return f"{start}-{100 if start == 80 else start + READINESS_BUCKET_SIZE - 1}"

    @staticmethod
    def _beta_summary(alpha: float, beta: float) -> tuple[float, float, float]:
        total = alpha + beta
        mean = alpha / total
        variance = alpha * beta / (total * total * (total + 1.0))
        margin = 1.96 * math.sqrt(max(variance, 0.0))
        return mean, max(0.0, mean - margin), min(1.0, mean + margin)

    @staticmethod
    def _beta_binomial_variance(count: int, alpha: float, beta: float) -> float:
        total = alpha + beta
        if count <= 0 or total <= 0:
            return 0.0
        return (
            count
            * alpha
            * beta
            * (total + count)
            / (total * total * (total + 1.0))
        )

    @staticmethod
    def _empty(
        *,
        segment: AudienceSegment,
        stage: str,
        event_type: str,
        horizon_hours: int,
        budget: int,
        evaluated_members: int = 0,
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "segment_id": segment.id,
            "segment_name": segment.name,
            "platform": segment.platform,
            "stage": stage,
            "event_type": event_type,
            "horizon_hours": horizon_hours,
            "requested_budget": budget,
            "evaluated_members": evaluated_members,
            "historical_samples": 0,
            "historical_positives": 0,
            "historical_observed_rate": 0.0,
            "expected_outcomes": 0.0,
            "expected_rate": 0.0,
            "confidence_low_outcomes": 0.0,
            "confidence_high_outcomes": 0.0,
            "confidence_low_rate": 0.0,
            "confidence_high_rate": 0.0,
            "frozen_history_ratio": 0.0,
            "evidence_coverage": {"exact": 0.0, "readiness": 0.0, "signal": 0.0, "global": 100.0 if evaluated_members else 0.0},
            "quality_status": "insufficient",
            "warnings": warnings,
            "evidence_rows": [],
        }

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
