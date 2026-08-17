from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.allocations.frontier_schemas import CapacityFrontierRequest
from app.features.allocations.service import (
    MAX_OFFERS,
    MAX_OFFERS_PER_SEGMENT,
    MAX_SEGMENTS,
    STABLE_GLOBAL_I2,
    CapacityAllocationService,
)
from app.features.experiments.contextual import ContextualIncrementalYieldService
from app.features.experiments.contextual_value import ContextualIncrementalBusinessValueService
from app.features.experiments.meta import IncrementalYieldMetaService
from app.features.experiments.value import IncrementalBusinessValueService
from app.features.segments.models import AudienceSegment
from app.features.segments.schemas import SegmentCriteria


class CapacityEconomicsFrontierService:
    """Estimate marginal causal value unlocked by progressively more capacity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.allocation = CapacityAllocationService(session)

    async def forecast(
        self,
        *,
        owner_id: UUID,
        payload: CapacityFrontierRequest,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        platform = payload.platform.strip().lower()
        event_type = payload.event_type.strip().lower().replace(" ", "_")
        objective = payload.objective
        max_capacity = max(payload.capacities)

        if objective == "incremental_business_value":
            assert payload.value_unit is not None
            global_result = await IncrementalBusinessValueService(self.session).analyze(
                owner_id=owner_id,
                event_type=event_type,
                value_unit=payload.value_unit,
                horizon_hours=payload.horizon_hours,
                aggregation=payload.value_aggregation or "sum",
                min_confidence=min_confidence,
            )
            if global_result["status"] == "insufficient":
                raise ValueError("Randomized business-value evidence is insufficient for capacity economics")
            contextual_result = await ContextualIncrementalBusinessValueService(self.session).analyze(
                owner_id=owner_id,
                event_type=event_type,
                value_unit=payload.value_unit,
                horizon_hours=payload.horizon_hours,
                aggregation=payload.value_aggregation or "sum",
                min_confidence=min_confidence,
                global_value=global_result,
            )
            contextual_rows = {
                (row["readiness_bucket"], row["strongest_signal_type"]): row
                for row in contextual_result["rows"]
            }
            global_effect = float(global_result["pooled_incremental_value_per_unit"])
            global_low = float(global_result["confidence_low_per_unit"])
            global_high = float(global_result["confidence_high_per_unit"])
            global_status = str(global_result["status"])
            global_i2 = float(global_result["i_squared_percent"])
            evidence_fn = self.allocation._value_evidence_for_member
        else:
            global_result = await IncrementalYieldMetaService(self.session).analyze(
                owner_id=owner_id,
                stage=payload.stage,
                event_type=event_type,
                horizon_hours=payload.horizon_hours,
                min_confidence=min_confidence,
            )
            if global_result["status"] == "insufficient":
                raise ValueError("Randomized causal evidence is insufficient for capacity economics")
            contextual_result = await ContextualIncrementalYieldService(self.session).analyze(
                owner_id=owner_id,
                stage=payload.stage,
                event_type=event_type,
                horizon_hours=payload.horizon_hours,
                min_confidence=min_confidence,
                global_meta=global_result,
            )
            contextual_rows = {
                (row["readiness_bucket"], row["strongest_signal_type"]): row
                for row in contextual_result["rows"]
            }
            global_effect = float(global_result["pooled_lift_percentage_points"]) / 100.0
            global_low = float(global_result["confidence_low_percentage_points"]) / 100.0
            global_high = float(global_result["confidence_high_percentage_points"]) / 100.0
            global_status = str(global_result["status"])
            global_i2 = float(global_result["i_squared_percent"])
            evidence_fn = self.allocation._evidence_for_member

        stable_global = global_status == "positive" and global_i2 < STABLE_GLOBAL_I2 and global_low > 0
        segments_result = await self.session.execute(
            select(AudienceSegment)
            .where(
                AudienceSegment.owner_id == owner_id,
                AudienceSegment.platform == platform,
                AudienceSegment.is_active.is_(True),
                AudienceSegment.last_refreshed_at.is_not(None),
                AudienceSegment.matched_count > 0,
            )
            .order_by(AudienceSegment.updated_at.desc())
            .limit(MAX_SEGMENTS)
        )
        segments = list(segments_result.scalars().all())
        if not segments:
            raise ValueError("No active materialized Opportunities are available")

        best_offer_by_member: dict[UUID, dict[str, Any]] = {}
        eligible_offer_count = 0
        offers_considered = 0
        candidate_pool_capped = False
        per_segment_target = min(max(max_capacity * 2, 2_000), MAX_OFFERS_PER_SEGMENT)

        for segment in segments:
            if offers_considered >= MAX_OFFERS:
                candidate_pool_capped = True
                break
            criteria = SegmentCriteria.model_validate(segment.criteria)
            limit = min(per_segment_target, max(MAX_OFFERS - offers_considered, 0))
            members = await self.allocation._ranked_members(
                segment_id=segment.id,
                criteria=criteria,
                limit=limit,
            )
            if segment.matched_count > limit:
                candidate_pool_capped = True
            for segment_rank, member in enumerate(members, start=1):
                if offers_considered >= MAX_OFFERS:
                    candidate_pool_capped = True
                    break
                offers_considered += 1
                evidence = evidence_fn(
                    member=member,
                    contextual_rows=contextual_rows,
                    global_effect=global_effect,
                    global_low=global_low,
                    global_high=global_high,
                    global_status=global_status,
                    stable_global=stable_global,
                    allocation_mode=payload.allocation_mode,
                )
                if evidence is None or float(evidence["low"]) <= 0:
                    continue
                eligible_offer_count += 1
                offer = {
                    "member_id": member.audience_member_id,
                    "segment_id": segment.id,
                    "segment_rank": segment_rank,
                    **evidence,
                }
                existing = best_offer_by_member.get(member.audience_member_id)
                if existing is None or self.allocation._offer_key(offer) > self.allocation._offer_key(existing):
                    best_offer_by_member[member.audience_member_id] = offer

        ranked = sorted(best_offer_by_member.values(), key=self.allocation._offer_key, reverse=True)
        overlap_removed = max(eligible_offer_count - len(best_offer_by_member), 0)
        warnings = ["one_person_one_frontier_offer_enforced"]
        if candidate_pool_capped:
            warnings.append("candidate_pool_capped_frontier_is_lower_bound")
        if global_status == "heterogeneous":
            warnings.append("global_causal_prior_heterogeneous")
        if objective == "incremental_business_value":
            warnings.extend(["single_value_unit_enforced", "verified_webhook_value_only"])

        points: list[dict[str, Any]] = []
        previous_count = 0
        previous_expected = 0.0
        previous_low = 0.0
        previous_high = 0.0
        recommended_capacity: int | None = None
        for requested in payload.capacities:
            selected = ranked[:requested]
            allocated_count = len(selected)
            cumulative_expected = sum(float(item["effect"]) for item in selected)
            cumulative_low = sum(float(item["low"]) for item in selected)
            cumulative_high = sum(float(item["high"]) for item in selected)
            marginal_count = max(allocated_count - previous_count, 0)
            marginal_expected = cumulative_expected - previous_expected
            marginal_low = cumulative_low - previous_low
            marginal_high = cumulative_high - previous_high
            marginal_per_action = marginal_low / marginal_count if marginal_count else None

            cumulative_cost = None
            cumulative_net = None
            marginal_cost = None
            marginal_net = None
            if payload.cost_per_action is not None:
                cumulative_cost = payload.cost_per_action * allocated_count
                cumulative_net = cumulative_low - cumulative_cost
                marginal_cost = payload.cost_per_action * marginal_count
                marginal_net = marginal_low - marginal_cost
                if marginal_count > 0 and marginal_net > 0:
                    recommended_capacity = requested

            points.append(
                {
                    "requested_capacity": requested,
                    "allocated_count": allocated_count,
                    "cumulative_expected": round(cumulative_expected, 4),
                    "cumulative_conservative": round(cumulative_low, 4),
                    "cumulative_upside": round(cumulative_high, 4),
                    "marginal_count": marginal_count,
                    "marginal_expected": round(marginal_expected, 4),
                    "marginal_conservative": round(marginal_low, 4),
                    "marginal_upside": round(marginal_high, 4),
                    "marginal_conservative_per_action": round(marginal_per_action, 6) if marginal_per_action is not None else None,
                    "cumulative_cost": round(cumulative_cost, 4) if cumulative_cost is not None else None,
                    "cumulative_conservative_net": round(cumulative_net, 4) if cumulative_net is not None else None,
                    "marginal_cost": round(marginal_cost, 4) if marginal_cost is not None else None,
                    "marginal_conservative_net": round(marginal_net, 4) if marginal_net is not None else None,
                }
            )
            previous_count = allocated_count
            previous_expected = cumulative_expected
            previous_low = cumulative_low
            previous_high = cumulative_high

        if payload.cost_per_action is None:
            recommendation_reason = "Provide cost_per_action to estimate the economically justified capacity ceiling."
        elif recommended_capacity is None:
            recommendation_reason = "No tested capacity block has positive conservative marginal value after action cost."
        else:
            recommendation_reason = "Largest tested capacity whose newest block still has positive conservative net value."

        return {
            "objective": objective,
            "value_unit": payload.value_unit,
            "event_type": event_type,
            "horizon_hours": payload.horizon_hours,
            "allocation_mode": payload.allocation_mode,
            "global_prior_status": global_status,
            "global_prior_i_squared": round(global_i2, 2),
            "unique_positive_candidates": len(ranked),
            "overlap_removed": overlap_removed,
            "candidate_pool_capped": candidate_pool_capped,
            "cost_per_action": payload.cost_per_action,
            "recommended_capacity": recommended_capacity,
            "recommendation_reason": recommendation_reason,
            "warnings": warnings,
            "points": points,
        }
