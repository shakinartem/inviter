from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.intelligence.models import AudienceMember, CommunityMembership, IntentSignal
from app.features.learning.models import ActionFeatureSnapshot, OutcomeEvent
from app.features.orchestration.models import ActionJob


SNAPSHOT_VERSION = "action-feature-v1"


class OutcomeLearningService:
    """Create immutable decision-time features and append-only outcome labels."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_action_snapshot(self, job_id: UUID) -> ActionFeatureSnapshot | None:
        existing_result = await self.session.execute(
            select(ActionFeatureSnapshot).where(ActionFeatureSnapshot.action_job_id == job_id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing

        job_result = await self.session.execute(select(ActionJob).where(ActionJob.id == job_id))
        job = job_result.scalar_one_or_none()
        if job is None:
            return None

        member_result = await self.session.execute(
            select(AudienceMember).where(AudienceMember.id == job.audience_member_id)
        )
        member = member_result.scalar_one_or_none()
        if member is None:
            return None

        signals_result = await self.session.execute(
            select(IntentSignal)
            .where(IntentSignal.audience_member_id == member.id)
            .order_by(IntentSignal.observed_at.desc())
            .limit(100)
        )
        recent_signals = list(signals_result.scalars().all())
        signal_count_result = await self.session.execute(
            select(func.count(IntentSignal.id)).where(IntentSignal.audience_member_id == member.id)
        )
        signal_count = int(signal_count_result.scalar() or 0)

        community_count_result = await self.session.execute(
            select(func.count(CommunityMembership.id)).where(
                CommunityMembership.audience_member_id == member.id
            )
        )
        communities_count = int(community_count_result.scalar() or 0)

        strongest_signal_type: str | None = None
        if recent_signals:
            strongest = max(
                recent_signals,
                key=lambda signal: float(signal.score or 0.0) * float(signal.confidence or 0.0),
            )
            strongest_signal_type = strongest.signal_type

        signal_type_counts = Counter(signal.signal_type for signal in recent_signals)
        intent_model_versions = sorted({signal.model_version for signal in recent_signals})
        latest_signal_at = recent_signals[0].observed_at if recent_signals else None

        captured_at = datetime.now(timezone.utc)
        scheduled_at = self._aware(job.scheduled_at)
        snapshot = ActionFeatureSnapshot(
            owner_id=job.owner_id,
            action_job_id=job.id,
            campaign_id=job.campaign_id,
            audience_member_id=member.id,
            platform=job.platform,
            action=job.action,
            captured_at=captured_at,
            first_transport_at=None,
            activity_score=member.activity_score,
            relevance_score=member.relevance_score,
            quality_score=member.quality_score,
            intent_score=member.intent_score,
            readiness_score=member.readiness_score,
            signal_count=signal_count,
            strongest_signal_type=strongest_signal_type,
            intent_model_versions=intent_model_versions or None,
            feature_payload={
                "recent_signal_type_counts": dict(signal_type_counts),
                "latest_signal_at": latest_signal_at.isoformat() if latest_signal_at else None,
                "communities_count": communities_count,
                "scheduled_hour_utc": scheduled_at.hour,
                "scheduled_weekday_utc": scheduled_at.weekday(),
                "max_attempts": job.max_attempts,
                "planner_activity_score": (job.payload or {}).get("activity_score"),
                "planner_readiness_score": (job.payload or {}).get("readiness_score"),
            },
            snapshot_version=SNAPSHOT_VERSION,
        )
        self.session.add(snapshot)
        await self.session.commit()
        await self.session.refresh(snapshot)
        return snapshot

    async def record_transport_result(
        self,
        job_id: UUID,
        result: dict[str, Any],
    ) -> OutcomeEvent | None:
        job_result = await self.session.execute(select(ActionJob).where(ActionJob.id == job_id))
        job = job_result.scalar_one_or_none()
        if job is None or job.attempts <= 0 or not job.result_code:
            return None

        snapshot = await self.ensure_action_snapshot(job.id)
        if snapshot is None:
            return None

        dedupe_key = f"transport:{job.id}:{job.attempts}:{job.result_code}"
        existing_result = await self.session.execute(
            select(OutcomeEvent).where(
                OutcomeEvent.owner_id == job.owner_id,
                OutcomeEvent.dedupe_key == dedupe_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing

        now = datetime.now(timezone.utc)
        if snapshot.first_transport_at is None:
            snapshot.first_transport_at = now

        event = OutcomeEvent(
            owner_id=job.owner_id,
            action_job_id=job.id,
            campaign_id=job.campaign_id,
            audience_member_id=job.audience_member_id,
            platform=job.platform,
            stage="transport",
            event_type=job.result_code.strip().lower(),
            success=bool(result.get("ok")),
            source="connector",
            confidence=1.0,
            value=None,
            observed_at=now,
            external_event_id=None,
            dedupe_key=dedupe_key,
            properties={
                "job_status": job.status,
                "attempt": job.attempts,
                "terminal": job.status in {"success", "failed", "cancelled"},
                "retry_scheduled": job.status == "retry_wait",
            },
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def record_observed_outcome(
        self,
        *,
        owner_id: UUID,
        action_job_id: UUID,
        stage: str,
        event_type: str,
        success: bool | None = True,
        source: str = "manual",
        confidence: float = 1.0,
        value: float | None = None,
        observed_at: datetime | None = None,
        external_event_id: str | None = None,
        idempotency_key: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> OutcomeEvent:
        job_result = await self.session.execute(
            select(ActionJob).where(
                ActionJob.id == action_job_id,
                ActionJob.owner_id == owner_id,
            )
        )
        job = job_result.scalar_one_or_none()
        if job is None:
            raise ValueError("Action job not found")

        normalized_stage = stage.strip().lower()
        normalized_type = event_type.strip().lower().replace(" ", "_")
        normalized_source = source.strip().lower().replace(" ", "_")
        if normalized_stage not in {"engagement", "business"}:
            raise ValueError("Observed outcomes must be engagement or business stage")
        if not normalized_type:
            raise ValueError("event_type is required")

        observed = self._aware(observed_at or datetime.now(timezone.utc))
        dedupe_key = self._external_dedupe_key(
            job_id=job.id,
            stage=normalized_stage,
            event_type=normalized_type,
            source=normalized_source,
            observed_at=observed,
            external_event_id=external_event_id,
            idempotency_key=idempotency_key,
        )
        existing_result = await self.session.execute(
            select(OutcomeEvent).where(
                OutcomeEvent.owner_id == owner_id,
                OutcomeEvent.dedupe_key == dedupe_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing

        # Ensure the pre-action vector exists even if this outcome arrives later
        # through a CRM/webhook/manual integration.
        await self.ensure_action_snapshot(job.id)

        event = OutcomeEvent(
            owner_id=owner_id,
            action_job_id=job.id,
            campaign_id=job.campaign_id,
            audience_member_id=job.audience_member_id,
            platform=job.platform,
            stage=normalized_stage,
            event_type=normalized_type,
            success=success,
            source=normalized_source,
            confidence=max(0.0, min(float(confidence), 1.0)),
            value=value,
            observed_at=observed,
            external_event_id=external_event_id,
            dedupe_key=dedupe_key,
            properties=properties,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def list_outcomes(
        self,
        *,
        owner_id: UUID,
        stage: str | None = None,
        event_type: str | None = None,
        campaign_id: UUID | None = None,
        audience_member_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[OutcomeEvent], int]:
        clauses = [OutcomeEvent.owner_id == owner_id]
        if stage:
            clauses.append(OutcomeEvent.stage == stage.strip().lower())
        if event_type:
            clauses.append(OutcomeEvent.event_type == event_type.strip().lower().replace(" ", "_"))
        if campaign_id:
            clauses.append(OutcomeEvent.campaign_id == campaign_id)
        if audience_member_id:
            clauses.append(OutcomeEvent.audience_member_id == audience_member_id)

        total_result = await self.session.execute(select(func.count(OutcomeEvent.id)).where(*clauses))
        total = int(total_result.scalar() or 0)
        result = await self.session.execute(
            select(OutcomeEvent)
            .where(*clauses)
            .order_by(OutcomeEvent.observed_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def overview(self, *, owner_id: UUID) -> dict[str, Any]:
        snapshot_count_result = await self.session.execute(
            select(func.count(ActionFeatureSnapshot.id)).where(ActionFeatureSnapshot.owner_id == owner_id)
        )
        stage_result = await self.session.execute(
            select(OutcomeEvent.stage, func.count(OutcomeEvent.id))
            .where(OutcomeEvent.owner_id == owner_id)
            .group_by(OutcomeEvent.stage)
        )
        return {
            "snapshots": int(snapshot_count_result.scalar() or 0),
            "events_by_stage": {stage: int(count) for stage, count in stage_result.all()},
        }

    async def calibration(
        self,
        *,
        owner_id: UUID,
        stage: str,
        event_type: str,
        horizon_hours: int = 168,
        bucket_size: int = 20,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Empirical outcome rate by decision-time readiness bucket.

        Only cohorts whose full observation horizon has elapsed are included, so
        recent actions are not silently mislabeled as negatives (right censoring).
        """
        now = datetime.now(timezone.utc)
        horizon = timedelta(hours=horizon_hours)
        mature_cutoff = now - horizon
        normalized_stage = stage.strip().lower()
        normalized_type = event_type.strip().lower().replace(" ", "_")

        snapshots_result = await self.session.execute(
            select(ActionFeatureSnapshot).where(
                ActionFeatureSnapshot.owner_id == owner_id,
                ActionFeatureSnapshot.first_transport_at.is_not(None),
                ActionFeatureSnapshot.first_transport_at <= mature_cutoff,
                ActionFeatureSnapshot.readiness_score.is_not(None),
            )
        )
        snapshots = list(snapshots_result.scalars().all())
        if not snapshots:
            return self._empty_calibration(
                normalized_stage,
                normalized_type,
                horizon_hours,
                bucket_size,
            )

        job_ids = [snapshot.action_job_id for snapshot in snapshots]
        events_result = await self.session.execute(
            select(OutcomeEvent).where(
                OutcomeEvent.owner_id == owner_id,
                OutcomeEvent.action_job_id.in_(job_ids),
                OutcomeEvent.stage == normalized_stage,
                OutcomeEvent.event_type == normalized_type,
                OutcomeEvent.confidence >= min_confidence,
            )
        )
        events_by_job: dict[UUID, list[OutcomeEvent]] = defaultdict(list)
        for event in events_result.scalars().all():
            if event.action_job_id is not None:
                events_by_job[event.action_job_id].append(event)

        bucket_stats: dict[int, dict[str, int]] = defaultdict(lambda: {"samples": 0, "positives": 0})
        signal_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"samples": 0, "positives": 0})
        total_positives = 0

        for snapshot in snapshots:
            first_transport = self._aware(snapshot.first_transport_at)
            horizon_end = first_transport + horizon
            positive = any(
                self._aware(event.observed_at) >= first_transport
                and self._aware(event.observed_at) <= horizon_end
                and event.success is not False
                for event in events_by_job.get(snapshot.action_job_id, [])
            )

            readiness = max(0.0, min(float(snapshot.readiness_score or 0.0), 100.0))
            start = min(int(readiness // bucket_size) * bucket_size, 100 - bucket_size)
            bucket_stats[start]["samples"] += 1
            if positive:
                bucket_stats[start]["positives"] += 1
                total_positives += 1

            signal_key = snapshot.strongest_signal_type or "no_intent_signal"
            signal_stats[signal_key]["samples"] += 1
            if positive:
                signal_stats[signal_key]["positives"] += 1

        buckets = [
            self._rate_row(
                label=f"{start}-{min(start + bucket_size, 100)}",
                samples=stats["samples"],
                positives=stats["positives"],
            )
            for start, stats in sorted(bucket_stats.items())
        ]
        by_signal = [
            self._rate_row(label=label, samples=stats["samples"], positives=stats["positives"])
            for label, stats in sorted(signal_stats.items(), key=lambda item: item[1]["samples"], reverse=True)
        ]

        return {
            "stage": normalized_stage,
            "event_type": normalized_type,
            "horizon_hours": horizon_hours,
            "bucket_size": bucket_size,
            "mature_samples": len(snapshots),
            "positives": total_positives,
            "observed_rate": round(total_positives / len(snapshots) * 100.0, 2),
            "buckets": buckets,
            "by_strongest_signal": by_signal,
        }

    @staticmethod
    def _rate_row(*, label: str, samples: int, positives: int) -> dict[str, Any]:
        rate = positives / samples if samples else 0.0
        low, high = OutcomeLearningService._wilson_interval(positives, samples)
        return {
            "label": label,
            "samples": samples,
            "positives": positives,
            "rate": round(rate * 100.0, 2),
            "confidence_low": round(low * 100.0, 2),
            "confidence_high": round(high * 100.0, 2),
        }

    @staticmethod
    def _wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
        if total <= 0:
            return 0.0, 0.0
        p = successes / total
        denominator = 1.0 + z * z / total
        center = (p + z * z / (2.0 * total)) / denominator
        margin = (
            z
            * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total)
            / denominator
        )
        return max(0.0, center - margin), min(1.0, center + margin)

    @staticmethod
    def _external_dedupe_key(
        *,
        job_id: UUID,
        stage: str,
        event_type: str,
        source: str,
        observed_at: datetime,
        external_event_id: str | None,
        idempotency_key: str | None,
    ) -> str:
        if idempotency_key:
            return f"idempotency:{source}:{idempotency_key}"[:255]
        if external_event_id:
            return f"external:{source}:{external_event_id}"[:255]
        raw = f"{job_id}|{stage}|{event_type}|{source}|{observed_at.isoformat()}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"derived:{digest}"

    @staticmethod
    def _empty_calibration(
        stage: str,
        event_type: str,
        horizon_hours: int,
        bucket_size: int,
    ) -> dict[str, Any]:
        return {
            "stage": stage,
            "event_type": event_type,
            "horizon_hours": horizon_hours,
            "bucket_size": bucket_size,
            "mature_samples": 0,
            "positives": 0,
            "observed_rate": 0.0,
            "buckets": [],
            "by_strongest_signal": [],
        }

    @staticmethod
    def _aware(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
