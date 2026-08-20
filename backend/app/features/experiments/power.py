from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from statistics import NormalDist
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.experiments.models import ExperimentAssignment
from app.features.experiments.service import CampaignExperimentService
from app.features.intelligence.models import AudienceMember
from app.features.learning.models import OutcomeEvent
from app.features.segments.models import AudienceSegment


MAX_BASELINE_HISTORY = 50_000
EVENT_QUERY_CHUNK = 4_000
MIN_BASELINE_SAMPLES = 30


class ExperimentPowerPlanner:
    """Plan randomized sample size before sacrificing treatment reach."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def plan(
        self,
        *,
        owner_id: UUID,
        segment_id: UUID,
        stage: str = "business",
        event_type: str = "converted",
        horizon_hours: int = 168,
        holdout_percentage: float = 10.0,
        action_budget: int = 1_000,
        target_lift_percentage_points: float = 2.0,
        alpha: float = 0.05,
        target_power: float = 0.8,
        baseline_rate_assumption: float | None = None,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        normalized_stage = stage.strip().lower()
        normalized_type = event_type.strip().lower().replace(" ", "_")
        if normalized_stage not in {"engagement", "business"}:
            raise ValueError("Power planning supports engagement or business outcomes only")
        if not normalized_type:
            raise ValueError("event_type is required")
        if horizon_hours < 1 or horizon_hours > 2160:
            raise ValueError("horizon_hours must be between 1 and 2160")
        if holdout_percentage <= 0 or holdout_percentage > 50:
            raise ValueError("holdout_percentage must be greater than 0 and at most 50")
        if action_budget < 1 or action_budget > 50_000:
            raise ValueError("action_budget must be between 1 and 50000")
        if target_lift_percentage_points <= 0 or target_lift_percentage_points >= 100:
            raise ValueError("target lift must be between 0 and 100 percentage points")
        if alpha <= 0 or alpha >= 0.5:
            raise ValueError("alpha must be between 0 and 0.5")
        if target_power <= 0.5 or target_power >= 1.0:
            raise ValueError("target_power must be between 0.5 and 1.0")
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
        if not segment.is_active or segment.last_refreshed_at is None:
            raise ValueError("Opportunity must be active and materialized")

        baseline_samples, baseline_positives = await self._mature_holdout_baseline(
            owner_id=owner_id,
            platform=segment.platform,
            stage=normalized_stage,
            event_type=normalized_type,
            horizon_hours=horizon_hours,
            min_confidence=min_confidence,
        )
        baseline_source = "missing"
        baseline_rate: float | None = None
        warnings: list[str] = []
        if baseline_samples >= MIN_BASELINE_SAMPLES:
            baseline_rate = baseline_positives / baseline_samples
            baseline_source = "mature_holdout_history"
        elif baseline_rate_assumption is not None:
            assumption = float(baseline_rate_assumption) / 100.0
            if assumption <= 0 or assumption >= 1:
                raise ValueError("baseline_rate_assumption must be between 0 and 100 percent")
            baseline_rate = assumption
            baseline_source = "explicit_assumption"
            warnings.append("baseline_is_user_assumption")
            if baseline_samples > 0:
                warnings.append("mature_holdout_history_too_small")
        else:
            warnings.append("baseline_rate_required")
            if baseline_samples > 0:
                warnings.append("mature_holdout_history_too_small")

        requested_pool = CampaignExperimentService.required_pool_size(
            action_budget=action_budget,
            holdout_percentage=holdout_percentage,
        )
        projected_total = min(segment.matched_count, requested_pool)
        full_pool_available = projected_total >= requested_pool
        projected_holdout = CampaignExperimentService.holdout_count_for_pool(
            pool_size=projected_total,
            action_budget=action_budget,
            holdout_percentage=holdout_percentage,
            full_pool_available=full_pool_available,
        ) if projected_total > 0 else 0
        projected_treatment = max(projected_total - projected_holdout, 0)

        if baseline_rate is None:
            return {
                "segment_id": segment.id,
                "segment_name": segment.name,
                "platform": segment.platform,
                "stage": normalized_stage,
                "event_type": normalized_type,
                "horizon_hours": horizon_hours,
                "holdout_percentage": holdout_percentage,
                "alpha": alpha,
                "target_power": target_power,
                "baseline_rate": None,
                "baseline_source": baseline_source,
                "baseline_samples": baseline_samples,
                "baseline_positives": baseline_positives,
                "target_lift_percentage_points": target_lift_percentage_points,
                "required_total_units": None,
                "required_treatment_units": None,
                "required_holdout_units": None,
                "available_segment_units": segment.matched_count,
                "requested_action_budget": action_budget,
                "projected_total_units": projected_total,
                "projected_treatment_units": projected_treatment,
                "projected_holdout_units": projected_holdout,
                "projected_mde_percentage_points": None,
                "adequately_powered": False,
                "status": "baseline_required",
                "warnings": warnings,
            }

        delta = target_lift_percentage_points / 100.0
        if baseline_rate + delta >= 1.0:
            warnings.append("target_lift_exceeds_probability_ceiling")
            required_total = None
        else:
            required_total = self.required_total_units(
                baseline_rate=baseline_rate,
                treatment_rate=baseline_rate + delta,
                holdout_fraction=holdout_percentage / 100.0,
                alpha=alpha,
                power=target_power,
            )

        required_holdout = None
        required_treatment = None
        if required_total is not None:
            required_holdout = max(1, int(math.ceil(required_total * holdout_percentage / 100.0)))
            required_treatment = required_total - required_holdout

        projected_mde = self.minimum_detectable_effect(
            baseline_rate=baseline_rate,
            treatment_units=projected_treatment,
            holdout_units=projected_holdout,
            alpha=alpha,
            power=target_power,
        )
        adequately_powered = (
            required_total is not None
            and projected_treatment > 0
            and projected_holdout > 0
            and projected_total >= required_total
        )

        if projected_holdout == 0 or projected_treatment == 0:
            status = "impossible"
            warnings.append("insufficient_units_for_two_arms")
        elif baseline_rate + delta >= 1.0:
            status = "impossible"
        elif adequately_powered:
            status = "adequately_powered"
        else:
            status = "underpowered"
            warnings.append("planned_experiment_underpowered_for_target_lift")
        if segment.matched_count < requested_pool:
            warnings.append("opportunity_smaller_than_requested_experiment_pool")
        if holdout_percentage < 15:
            warnings.append("small_holdout_increases_required_total_sample")

        return {
            "segment_id": segment.id,
            "segment_name": segment.name,
            "platform": segment.platform,
            "stage": normalized_stage,
            "event_type": normalized_type,
            "horizon_hours": horizon_hours,
            "holdout_percentage": holdout_percentage,
            "alpha": alpha,
            "target_power": target_power,
            "baseline_rate": round(baseline_rate * 100.0, 3),
            "baseline_source": baseline_source,
            "baseline_samples": baseline_samples,
            "baseline_positives": baseline_positives,
            "target_lift_percentage_points": target_lift_percentage_points,
            "required_total_units": required_total,
            "required_treatment_units": required_treatment,
            "required_holdout_units": required_holdout,
            "available_segment_units": segment.matched_count,
            "requested_action_budget": action_budget,
            "projected_total_units": projected_total,
            "projected_treatment_units": projected_treatment,
            "projected_holdout_units": projected_holdout,
            "projected_mde_percentage_points": round(projected_mde * 100.0, 3) if projected_mde is not None else None,
            "adequately_powered": adequately_powered,
            "status": status,
            "warnings": warnings,
        }

    async def _mature_holdout_baseline(
        self,
        *,
        owner_id: UUID,
        platform: str,
        stage: str,
        event_type: str,
        horizon_hours: int,
        min_confidence: float,
    ) -> tuple[int, int]:
        mature_cutoff = datetime.now(timezone.utc) - timedelta(hours=horizon_hours)
        result = await self.session.execute(
            select(ExperimentAssignment)
            .join(AudienceMember, AudienceMember.id == ExperimentAssignment.audience_member_id)
            .where(
                ExperimentAssignment.owner_id == owner_id,
                ExperimentAssignment.variant == "holdout",
                ExperimentAssignment.assigned_at <= mature_cutoff,
                AudienceMember.platform == platform,
            )
            .order_by(ExperimentAssignment.assigned_at.desc())
            .limit(MAX_BASELINE_HISTORY)
        )
        assignments = list(result.scalars().all())
        if not assignments:
            return 0, 0

        by_id = {item.id: item for item in assignments}
        positive_ids: set[UUID] = set()
        ids = list(by_id)
        horizon = timedelta(hours=horizon_hours)
        for start in range(0, len(ids), EVENT_QUERY_CHUNK):
            chunk = ids[start : start + EVENT_QUERY_CHUNK]
            events_result = await self.session.execute(
                select(OutcomeEvent).where(
                    OutcomeEvent.owner_id == owner_id,
                    OutcomeEvent.experiment_assignment_id.in_(chunk),
                    OutcomeEvent.stage == stage,
                    OutcomeEvent.event_type == event_type,
                    OutcomeEvent.success.is_(True),
                    OutcomeEvent.confidence >= min_confidence,
                )
            )
            for event in events_result.scalars().all():
                assignment = by_id.get(event.experiment_assignment_id)
                if assignment is None:
                    continue
                observed = self._aware(event.observed_at)
                assigned = self._aware(assignment.assigned_at)
                if assigned <= observed <= assigned + horizon:
                    positive_ids.add(assignment.id)
        return len(assignments), len(positive_ids)

    @staticmethod
    def required_total_units(
        *,
        baseline_rate: float,
        treatment_rate: float,
        holdout_fraction: float,
        alpha: float = 0.05,
        power: float = 0.8,
    ) -> int:
        q = float(holdout_fraction)
        r = 1.0 - q
        if q <= 0 or r <= 0:
            raise ValueError("both randomized arms require non-zero allocation")
        p0 = float(baseline_rate)
        p1 = float(treatment_rate)
        if not (0 < p0 < 1 and 0 < p1 < 1 and p1 != p0):
            raise ValueError("baseline and treatment rates must differ and remain within (0,1)")
        z_alpha = NormalDist().inv_cdf(1.0 - alpha / 2.0)
        z_power = NormalDist().inv_cdf(power)
        pooled = r * p1 + q * p0
        null_variance = pooled * (1.0 - pooled) * (1.0 / r + 1.0 / q)
        alt_variance = p1 * (1.0 - p1) / r + p0 * (1.0 - p0) / q
        numerator = z_alpha * math.sqrt(null_variance) + z_power * math.sqrt(alt_variance)
        total = numerator * numerator / ((p1 - p0) ** 2)
        return max(2, int(math.ceil(total)))

    @classmethod
    def minimum_detectable_effect(
        cls,
        *,
        baseline_rate: float,
        treatment_units: int,
        holdout_units: int,
        alpha: float = 0.05,
        power: float = 0.8,
    ) -> float | None:
        total = int(treatment_units) + int(holdout_units)
        if treatment_units < 1 or holdout_units < 1 or total < 2:
            return None
        q = holdout_units / total
        maximum = min(0.95, 1.0 - baseline_rate - 1e-6)
        if maximum <= 0:
            return None
        if cls.required_total_units(
            baseline_rate=baseline_rate,
            treatment_rate=baseline_rate + maximum,
            holdout_fraction=q,
            alpha=alpha,
            power=power,
        ) > total:
            return None
        low = 1e-5
        high = maximum
        for _ in range(50):
            mid = (low + high) / 2.0
            required = cls.required_total_units(
                baseline_rate=baseline_rate,
                treatment_rate=baseline_rate + mid,
                holdout_fraction=q,
                alpha=alpha,
                power=power,
            )
            if required <= total:
                high = mid
            else:
                low = mid
        return high

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
