from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.experiments.contextual import ContextualIncrementalYieldService
from app.features.experiments.meta import IncrementalYieldMetaService
from app.features.segments.models import AudienceSegment, AudienceSegmentMember
from app.features.segments.schemas import SegmentCriteria


MAX_SEGMENTS = 20
READY_CONTEXTUAL_COVERAGE = 70.0
LIMITED_CONTEXTUAL_COVERAGE = 30.0


class CausalOpportunityPortfolioService:
    """Allocate action capacity using randomized incremental-yield evidence.

    Replicated contextual evidence is allowed to move a segment away from the
    global randomized prior. Exploratory contextual rows are tracked for learning
    coverage but never change the allocation estimate until replicated.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def forecast(
        self,
        *,
        owner_id: UUID,
        stage: str = "business",
        event_type: str = "converted",
        horizon_hours: int = 168,
        action_budget: int = 1_000,
        platform: str | None = None,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        normalized_stage = stage.strip().lower()
        normalized_type = event_type.strip().lower().replace(" ", "_")
        if normalized_stage not in {"engagement", "business"}:
            raise ValueError("Causal Portfolio supports engagement or business outcomes only")
        if not normalized_type:
            raise ValueError("event_type is required")
        if horizon_hours < 1 or horizon_hours > 2160:
            raise ValueError("horizon_hours must be between 1 and 2160")
        if action_budget < 1 or action_budget > 50_000:
            raise ValueError("action_budget must be between 1 and 50000")
        if min_confidence < 0 or min_confidence > 1:
            raise ValueError("min_confidence must be between 0 and 1")

        global_meta = await IncrementalYieldMetaService(self.session).analyze(
            owner_id=owner_id,
            stage=normalized_stage,
            event_type=normalized_type,
            horizon_hours=horizon_hours,
            min_confidence=min_confidence,
        )
        contextual = await ContextualIncrementalYieldService(self.session).analyze(
            owner_id=owner_id,
            stage=normalized_stage,
            event_type=normalized_type,
            horizon_hours=horizon_hours,
            min_confidence=min_confidence,
        )

        global_effect = float(global_meta["pooled_lift_percentage_points"]) / 100.0
        global_low = float(global_meta["confidence_low_percentage_points"]) / 100.0
        global_high = float(global_meta["confidence_high_percentage_points"]) / 100.0
        contextual_rows = {
            (row["readiness_bucket"], row["strongest_signal_type"]): row
            for row in contextual["rows"]
        }

        segment_clauses = [
            AudienceSegment.owner_id == owner_id,
            AudienceSegment.is_active.is_(True),
            AudienceSegment.last_refreshed_at.is_not(None),
            AudienceSegment.matched_count > 0,
        ]
        if platform:
            segment_clauses.append(AudienceSegment.platform == platform.strip().lower())
        segments_result = await self.session.execute(
            select(AudienceSegment)
            .where(*segment_clauses)
            .order_by(AudienceSegment.matched_count.desc(), AudienceSegment.updated_at.desc())
            .limit(MAX_SEGMENTS)
        )
        segments = list(segments_result.scalars().all())

        rows: list[dict[str, Any]] = []
        for segment in segments:
            criteria = SegmentCriteria.model_validate(segment.criteria)
            members = await self._ranked_members(
                segment_id=segment.id,
                criteria=criteria,
                budget=action_budget,
            )
            if not members:
                continue

            expected = 0.0
            conservative = 0.0
            upside = 0.0
            coverage = Counter()
            segment_warnings: list[str] = []

            for member in members:
                bucket_label = self._bucket_label(member.readiness_score)
                signal = member.strongest_signal_type or "no_intent_signal"
                contextual_row = contextual_rows.get((bucket_label, signal))

                if contextual_row and contextual_row["evidence_status"] == "replicated":
                    effect = float(contextual_row["shrunk_lift_percentage_points"]) / 100.0
                    low = float(contextual_row["confidence_low_percentage_points"]) / 100.0
                    high = float(contextual_row["confidence_high_percentage_points"]) / 100.0
                    coverage["replicated"] += 1
                else:
                    effect = global_effect
                    low = global_low
                    high = global_high
                    if contextual_row:
                        coverage["exploratory"] += 1
                    else:
                        coverage["global"] += 1

                expected += effect
                conservative += low
                upside += high

            evaluated = len(members)
            replicated_pct = coverage["replicated"] / evaluated * 100.0
            exploratory_pct = coverage["exploratory"] / evaluated * 100.0
            global_pct = coverage["global"] / evaluated * 100.0

            if global_meta["status"] == "insufficient":
                evidence_status = "insufficient"
                segment_warnings.append("global_randomized_prior_insufficient")
            elif replicated_pct >= READY_CONTEXTUAL_COVERAGE:
                evidence_status = "ready"
            elif replicated_pct >= LIMITED_CONTEXTUAL_COVERAGE:
                evidence_status = "limited"
                segment_warnings.append("partial_replicated_context_coverage")
            else:
                evidence_status = "limited"
                segment_warnings.append("mostly_global_causal_fallback")

            if global_meta["status"] == "heterogeneous" and replicated_pct < READY_CONTEXTUAL_COVERAGE:
                segment_warnings.append("heterogeneous_global_prior_with_low_context_coverage")
                evidence_status = "limited" if evidence_status != "insufficient" else evidence_status

            rows.append(
                {
                    "segment_id": segment.id,
                    "segment_name": segment.name,
                    "matched_count": segment.matched_count,
                    "evaluated_members": evaluated,
                    "expected_incremental_outcomes": round(expected, 2),
                    "conservative_incremental_outcomes": round(conservative, 2),
                    "upside_incremental_outcomes": round(upside, 2),
                    "expected_incremental_rate": round(expected / evaluated * 100.0, 3),
                    "conservative_incremental_rate": round(conservative / evaluated * 100.0, 3),
                    "replicated_context_coverage": round(replicated_pct, 2),
                    "exploratory_context_coverage": round(exploratory_pct, 2),
                    "global_fallback_coverage": round(global_pct, 2),
                    "evidence_status": evidence_status,
                    "warnings": segment_warnings,
                }
            )

        rows.sort(
            key=lambda row: (
                row["evidence_status"] == "ready",
                row["conservative_incremental_outcomes"],
                row["expected_incremental_outcomes"],
                row["replicated_context_coverage"],
            ),
            reverse=True,
        )
        for index, row in enumerate(rows, start=1):
            row["rank"] = index

        recommendation = next(
            (
                row
                for row in rows
                if row["evidence_status"] == "ready"
                and row["replicated_context_coverage"] >= READY_CONTEXTUAL_COVERAGE
                and row["conservative_incremental_outcomes"] > 0
            ),
            None,
        )

        warnings = ["audience_overlap_not_deduplicated", "causal_estimates_depend_on_randomized_history"]
        if global_meta["status"] == "heterogeneous":
            warnings.append("global_causal_effect_is_heterogeneous")
        if recommendation is None and rows:
            warnings.append("no_decision_grade_causal_allocation")
        if not rows:
            warnings.append("no_materialized_opportunities")

        return {
            "stage": normalized_stage,
            "event_type": normalized_type,
            "horizon_hours": horizon_hours,
            "action_budget": action_budget,
            "global_prior_status": global_meta["status"],
            "global_prior_lift_percentage_points": global_meta["pooled_lift_percentage_points"],
            "global_prior_i_squared_percent": global_meta["i_squared_percent"],
            "recommendation_segment_id": recommendation["segment_id"] if recommendation else None,
            "recommendation_name": recommendation["segment_name"] if recommendation else None,
            "ranking_basis": "conservative_contextual_incremental_outcomes",
            "warnings": warnings,
            "rows": rows,
        }

    async def _ranked_members(
        self,
        *,
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

    @staticmethod
    def _bucket_label(readiness_score: float | None) -> str:
        score = max(0.0, min(float(readiness_score or 0.0), 100.0))
        start = min(int(score // 20) * 20, 80)
        return f"{start}-{100 if start == 80 else start + 19}"
