from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.allocations.models import CapacityAllocationAssignment, CapacityAllocationPlan
from app.features.experiments.contextual import ContextualIncrementalYieldService
from app.features.experiments.meta import IncrementalYieldMetaService
from app.features.segments.models import AudienceSegment, AudienceSegmentMember
from app.features.segments.schemas import SegmentCriteria
from app.features.allocations.schemas import CapacityAllocationCreate


MAX_SEGMENTS = 20
MAX_OFFERS = 100_000
MAX_OFFERS_PER_SEGMENT = 10_000
STABLE_GLOBAL_I2 = 30.0


class CapacityAllocationService:
    """Freeze a one-person-one-action allocation across competing Opportunities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_plan(
        self,
        *,
        owner_id: UUID,
        payload: CapacityAllocationCreate,
        min_confidence: float = 0.5,
    ) -> CapacityAllocationPlan:
        platform = payload.platform.strip().lower()
        event_type = payload.event_type.strip().lower().replace(" ", "_")
        global_meta = await IncrementalYieldMetaService(self.session).analyze(
            owner_id=owner_id,
            stage=payload.stage,
            event_type=event_type,
            horizon_hours=payload.horizon_hours,
            min_confidence=min_confidence,
        )
        if global_meta["status"] == "insufficient":
            raise ValueError("Randomized causal evidence is insufficient for joint allocation")

        contextual = await ContextualIncrementalYieldService(self.session).analyze(
            owner_id=owner_id,
            stage=payload.stage,
            event_type=event_type,
            horizon_hours=payload.horizon_hours,
            min_confidence=min_confidence,
            global_meta=global_meta,
        )
        contextual_rows = {
            (row["readiness_bucket"], row["strongest_signal_type"]): row
            for row in contextual["rows"]
        }
        global_effect = float(global_meta["pooled_lift_percentage_points"]) / 100.0
        global_low = float(global_meta["confidence_low_percentage_points"]) / 100.0
        global_high = float(global_meta["confidence_high_percentage_points"]) / 100.0
        stable_global = (
            global_meta["status"] == "positive"
            and float(global_meta["i_squared_percent"]) < STABLE_GLOBAL_I2
            and global_low > 0
        )

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
        offers_considered = 0
        candidate_pool_capped = False
        source_snapshot: dict[str, Any] = {"segments": []}

        for segment in segments:
            criteria = SegmentCriteria.model_validate(segment.criteria)
            per_segment_limit = min(
                max(payload.total_capacity * 2, 2_000),
                MAX_OFFERS_PER_SEGMENT,
                max(MAX_OFFERS - offers_considered, 0),
            )
            if per_segment_limit <= 0:
                candidate_pool_capped = True
                break
            members = await self._ranked_members(
                segment_id=segment.id,
                criteria=criteria,
                limit=per_segment_limit,
            )
            if segment.matched_count > per_segment_limit:
                candidate_pool_capped = True
            source_snapshot["segments"].append(
                {
                    "segment_id": str(segment.id),
                    "name": segment.name,
                    "refresh_sequence": segment.refresh_count,
                    "matched_count": segment.matched_count,
                    "criteria": segment.criteria,
                }
            )

            for segment_rank, member in enumerate(members, start=1):
                if offers_considered >= MAX_OFFERS:
                    candidate_pool_capped = True
                    break
                offers_considered += 1
                evidence = self._evidence_for_member(
                    member=member,
                    contextual_rows=contextual_rows,
                    global_effect=global_effect,
                    global_low=global_low,
                    global_high=global_high,
                    global_status=global_meta["status"],
                    stable_global=stable_global,
                    allocation_mode=payload.allocation_mode,
                )
                if evidence is None:
                    continue
                if payload.require_positive_conservative and evidence["low"] <= 0:
                    continue

                offer = {
                    "segment": segment,
                    "member": member,
                    "segment_rank": segment_rank,
                    **evidence,
                }
                existing = best_offer_by_member.get(member.audience_member_id)
                if existing is None or self._offer_key(offer) > self._offer_key(existing):
                    best_offer_by_member[member.audience_member_id] = offer

        unique_candidates = len(best_offer_by_member)
        ranked_offers = sorted(
            best_offer_by_member.values(),
            key=self._offer_key,
            reverse=True,
        )
        allocated = ranked_offers[: payload.total_capacity]

        expected = sum(float(offer["effect"]) for offer in allocated)
        conservative = sum(float(offer["low"]) for offer in allocated)
        upside = sum(float(offer["high"]) for offer in allocated)
        replicated_count = sum(offer["source"] == "replicated_context" for offer in allocated)
        replicated_coverage = (
            replicated_count / len(allocated) * 100.0 if allocated else 0.0
        )
        warnings = ["one_person_one_allocation_enforced"]
        if candidate_pool_capped:
            warnings.append("candidate_pool_capped_not_global_optimum")
        if payload.allocation_mode == "coverage_expansion":
            warnings.append("global_prior_fallback_allowed_for_coverage")
        if global_meta["status"] == "heterogeneous":
            warnings.append("global_causal_prior_heterogeneous")
        duplicate_offers_removed = max(offers_considered - unique_candidates, 0)
        unallocated_capacity = max(payload.total_capacity - len(allocated), 0)
        if unallocated_capacity:
            warnings.append("positive_decision_grade_supply_below_capacity")

        now = datetime.now(timezone.utc)
        plan = CapacityAllocationPlan(
            owner_id=owner_id,
            name=payload.name.strip(),
            platform=platform,
            stage=payload.stage,
            event_type=event_type,
            horizon_hours=payload.horizon_hours,
            total_capacity=payload.total_capacity,
            allocation_mode=payload.allocation_mode,
            require_positive_conservative=payload.require_positive_conservative,
            status="frozen",
            evidence_version="causal-allocation-v1",
            offers_considered=offers_considered,
            unique_candidates=unique_candidates,
            duplicate_offers_removed=duplicate_offers_removed,
            allocated_count=len(allocated),
            unallocated_capacity=unallocated_capacity,
            expected_incremental_outcomes=round(expected, 4),
            conservative_incremental_outcomes=round(conservative, 4),
            upside_incremental_outcomes=round(upside, 4),
            replicated_context_coverage=round(replicated_coverage, 2),
            global_prior_status=global_meta["status"],
            global_prior_lift=global_meta["pooled_lift_percentage_points"],
            global_prior_i_squared=global_meta["i_squared_percent"],
            candidate_pool_capped=candidate_pool_capped,
            warnings=warnings,
            source_snapshot=source_snapshot,
            frozen_at=now,
        )
        self.session.add(plan)
        await self.session.flush()

        for allocation_rank, offer in enumerate(allocated, start=1):
            segment = offer["segment"]
            member = offer["member"]
            self.session.add(
                CapacityAllocationAssignment(
                    plan_id=plan.id,
                    owner_id=owner_id,
                    segment_id=segment.id,
                    audience_member_id=member.audience_member_id,
                    allocation_rank=allocation_rank,
                    segment_rank=offer["segment_rank"],
                    segment_name_snapshot=segment.name,
                    segment_refresh_sequence=segment.refresh_count,
                    activity_score=member.activity_score,
                    relevance_score=member.relevance_score,
                    intent_score=member.intent_score,
                    readiness_score=member.readiness_score,
                    strongest_signal_type=member.strongest_signal_type,
                    match_reasons=member.match_reasons,
                    evidence_source=offer["source"],
                    context_key=offer["context_key"],
                    expected_incremental_probability=offer["effect"],
                    conservative_incremental_probability=offer["low"],
                    upside_incremental_probability=offer["high"],
                )
            )

        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    async def list_plans(
        self,
        *,
        owner_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CapacityAllocationPlan], int]:
        total = int(
            (
                await self.session.execute(
                    select(func.count(CapacityAllocationPlan.id)).where(
                        CapacityAllocationPlan.owner_id == owner_id
                    )
                )
            ).scalar()
            or 0
        )
        result = await self.session.execute(
            select(CapacityAllocationPlan)
            .where(CapacityAllocationPlan.owner_id == owner_id)
            .order_by(CapacityAllocationPlan.frozen_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_plan(self, *, owner_id: UUID, plan_id: UUID) -> CapacityAllocationPlan | None:
        result = await self.session.execute(
            select(CapacityAllocationPlan).where(
                CapacityAllocationPlan.id == plan_id,
                CapacityAllocationPlan.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def assignments(
        self,
        *,
        owner_id: UUID,
        plan_id: UUID,
        segment_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[CapacityAllocationAssignment], int]:
        plan = await self.get_plan(owner_id=owner_id, plan_id=plan_id)
        if plan is None:
            raise ValueError("Allocation plan not found")
        clauses = [CapacityAllocationAssignment.plan_id == plan_id]
        if segment_id:
            clauses.append(CapacityAllocationAssignment.segment_id == segment_id)
        total = int(
            (
                await self.session.execute(
                    select(func.count(CapacityAllocationAssignment.id)).where(*clauses)
                )
            ).scalar()
            or 0
        )
        result = await self.session.execute(
            select(CapacityAllocationAssignment)
            .where(*clauses)
            .order_by(CapacityAllocationAssignment.allocation_rank.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def _ranked_members(
        self,
        *,
        segment_id: UUID,
        criteria: SegmentCriteria,
        limit: int,
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
            .limit(limit)
        )
        return list(result.scalars().all())

    @classmethod
    def _evidence_for_member(
        cls,
        *,
        member: AudienceSegmentMember,
        contextual_rows: dict[tuple[str, str], dict[str, Any]],
        global_effect: float,
        global_low: float,
        global_high: float,
        global_status: str,
        stable_global: bool,
        allocation_mode: str,
    ) -> dict[str, Any] | None:
        bucket = cls._bucket_label(member.readiness_score)
        signal = member.strongest_signal_type or "no_intent_signal"
        row = contextual_rows.get((bucket, signal))
        if row and row["evidence_status"] == "replicated":
            return {
                "source": "replicated_context",
                "context_key": f"{bucket}:{signal}",
                "effect": float(row["shrunk_lift_percentage_points"]) / 100.0,
                "low": float(row["confidence_low_percentage_points"]) / 100.0,
                "high": float(row["confidence_high_percentage_points"]) / 100.0,
            }
        if allocation_mode == "decision_grade" and not stable_global:
            return None
        if global_status == "insufficient":
            return None
        return {
            "source": "stable_global_prior" if stable_global else "global_prior_fallback",
            "context_key": f"{bucket}:{signal}",
            "effect": global_effect,
            "low": global_low,
            "high": global_high,
        }

    @staticmethod
    def _offer_key(offer: dict[str, Any]) -> tuple[float, float, int, int]:
        source_priority = 2 if offer["source"] == "replicated_context" else 1
        return (
            float(offer["low"]),
            float(offer["effect"]),
            source_priority,
            -int(offer["segment_rank"]),
        )

    @staticmethod
    def _bucket_label(readiness_score: float | None) -> str:
        score = max(0.0, min(float(readiness_score or 0.0), 100.0))
        start = min(int(score // 20) * 20, 80)
        return f"{start}-{100 if start == 80 else start + 19}"
