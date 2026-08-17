from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.experiments.models import CampaignExperiment, ExperimentAssignment
from app.features.inviter.models import InviteCampaign
from app.features.learning.models import OutcomeEvent


MIN_ARM_SIZE = 30
MAX_EXPERIMENTS = 50
MAX_ASSIGNMENTS = 100_000
HETEROGENEITY_THRESHOLD = 50.0
VARIANCE_FLOOR = 1e-9


class IncrementalBusinessValueService:
    """Pool randomized treatment-minus-holdout business value differences."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def analyze(
        self,
        *,
        owner_id: UUID,
        event_type: str,
        value_unit: str,
        horizon_hours: int = 168,
        aggregation: str = "sum",
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        normalized_type = event_type.strip().lower().replace(" ", "_")
        normalized_unit = value_unit.strip().upper()
        normalized_aggregation = aggregation.strip().lower()
        if not normalized_type:
            raise ValueError("event_type is required")
        if not normalized_unit or len(normalized_unit) > 16:
            raise ValueError("value_unit is required and must be at most 16 characters")
        if normalized_aggregation not in {"sum", "max"}:
            raise ValueError("aggregation must be sum or max")
        if horizon_hours < 1 or horizon_hours > 2160:
            raise ValueError("horizon_hours must be between 1 and 2160")
        if min_confidence < 0 or min_confidence > 1:
            raise ValueError("min_confidence must be between 0 and 1")

        mature_cutoff = datetime.now(timezone.utc) - timedelta(hours=horizon_hours)
        experiments_result = await self.session.execute(
            select(CampaignExperiment, InviteCampaign)
            .join(InviteCampaign, InviteCampaign.id == CampaignExperiment.campaign_id)
            .where(
                CampaignExperiment.owner_id == owner_id,
                CampaignExperiment.status == "assigned",
                CampaignExperiment.assigned_at.is_not(None),
                CampaignExperiment.assigned_at <= mature_cutoff,
            )
            .order_by(CampaignExperiment.assigned_at.desc())
            .limit(MAX_EXPERIMENTS)
        )
        experiment_rows = list(experiments_result.all())
        if not experiment_rows:
            return self._empty(normalized_type, normalized_unit, horizon_hours, normalized_aggregation)

        experiment_by_id = {experiment.id: (experiment, campaign) for experiment, campaign in experiment_rows}
        assignments_result = await self.session.execute(
            select(ExperimentAssignment)
            .where(
                ExperimentAssignment.owner_id == owner_id,
                ExperimentAssignment.experiment_id.in_(list(experiment_by_id)),
            )
            .order_by(ExperimentAssignment.assigned_at.desc())
            .limit(MAX_ASSIGNMENTS + 1)
        )
        loaded = list(assignments_result.scalars().all())
        capped = len(loaded) > MAX_ASSIGNMENTS
        assignments = loaded[:MAX_ASSIGNMENTS]

        by_experiment: dict[UUID, list[ExperimentAssignment]] = defaultdict(list)
        by_assignment_id: dict[UUID, ExperimentAssignment] = {}
        by_campaign_member: dict[tuple[UUID, UUID], ExperimentAssignment] = {}
        for assignment in assignments:
            by_experiment[assignment.experiment_id].append(assignment)
            by_assignment_id[assignment.id] = assignment
            by_campaign_member[(assignment.campaign_id, assignment.audience_member_id)] = assignment

        complete_experiment_ids = {
            experiment_id
            for experiment_id, units in by_experiment.items()
            if len(units) == experiment_by_id[experiment_id][0].candidate_pool_size
        }
        incomplete = len(by_experiment) - len(complete_experiment_ids)
        complete_assignments = [
            assignment for assignment in assignments if assignment.experiment_id in complete_experiment_ids
        ]
        complete_by_id = {assignment.id: assignment for assignment in complete_assignments}
        values_by_assignment: dict[UUID, list[float]] = defaultdict(list)
        horizon = timedelta(hours=horizon_hours)

        if complete_experiment_ids:
            campaign_ids = [experiment_by_id[experiment_id][0].campaign_id for experiment_id in complete_experiment_ids]
            earliest = min(
                self._aware(experiment_by_id[experiment_id][0].assigned_at)
                for experiment_id in complete_experiment_ids
                if experiment_by_id[experiment_id][0].assigned_at is not None
            )
            latest = max(
                self._aware(experiment_by_id[experiment_id][0].assigned_at) + horizon
                for experiment_id in complete_experiment_ids
                if experiment_by_id[experiment_id][0].assigned_at is not None
            )
            events_result = await self.session.execute(
                select(OutcomeEvent).where(
                    OutcomeEvent.owner_id == owner_id,
                    OutcomeEvent.campaign_id.in_(campaign_ids),
                    OutcomeEvent.stage == "business",
                    OutcomeEvent.event_type == normalized_type,
                    OutcomeEvent.success.is_(True),
                    OutcomeEvent.source == "webhook",
                    OutcomeEvent.confidence >= min_confidence,
                    OutcomeEvent.value.is_not(None),
                    OutcomeEvent.value_unit == normalized_unit,
                    OutcomeEvent.observed_at >= earliest,
                    OutcomeEvent.observed_at <= latest,
                )
            )
            for event in events_result.scalars().all():
                assignment = None
                if event.experiment_assignment_id is not None:
                    assignment = complete_by_id.get(event.experiment_assignment_id)
                if assignment is None:
                    assignment = by_campaign_member.get((event.campaign_id, event.audience_member_id))
                if assignment is None or assignment.experiment_id not in complete_experiment_ids:
                    continue
                observed = self._aware(event.observed_at)
                assigned = self._aware(assignment.assigned_at)
                if assigned <= observed <= assigned + horizon:
                    values_by_assignment[assignment.id].append(float(event.value or 0.0))

        aggregated_value: dict[UUID, float] = {}
        for assignment in complete_assignments:
            values = values_by_assignment.get(assignment.id, [])
            if not values:
                aggregated_value[assignment.id] = 0.0
            elif normalized_aggregation == "max":
                aggregated_value[assignment.id] = max(values)
            else:
                aggregated_value[assignment.id] = sum(values)

        effects: list[dict[str, Any]] = []
        for experiment_id in complete_experiment_ids:
            experiment, campaign = experiment_by_id[experiment_id]
            units = by_experiment[experiment_id]
            treatment = [aggregated_value[item.id] for item in units if item.variant == "treatment"]
            holdout = [aggregated_value[item.id] for item in units if item.variant == "holdout"]
            if len(treatment) < MIN_ARM_SIZE or len(holdout) < MIN_ARM_SIZE:
                continue
            treatment_mean = fmean(treatment)
            holdout_mean = fmean(holdout)
            variance = max(
                self._sample_variance(treatment) / len(treatment)
                + self._sample_variance(holdout) / len(holdout),
                VARIANCE_FLOOR,
            )
            effects.append(
                {
                    "experiment_id": experiment.id,
                    "campaign_id": campaign.id,
                    "campaign_title": campaign.title,
                    "treatment_units": len(treatment),
                    "holdout_units": len(holdout),
                    "treatment_mean_value": treatment_mean,
                    "holdout_mean_value": holdout_mean,
                    "effect": treatment_mean - holdout_mean,
                    "variance": variance,
                }
            )

        warnings: list[str] = ["verified_webhook_value_only"]
        if capped:
            warnings.append("assignment_history_capped")
        if incomplete:
            warnings.append("partial_experiments_excluded")
        if len(effects) < 2:
            warnings.append("fewer_than_two_mature_value_experiments")
            return self._insufficient(
                normalized_type,
                normalized_unit,
                horizon_hours,
                normalized_aggregation,
                len(experiment_rows),
                effects,
                warnings,
            )

        fixed_weights = [1.0 / effect["variance"] for effect in effects]
        fixed_mean = sum(w * effect["effect"] for w, effect in zip(fixed_weights, effects)) / sum(fixed_weights)
        q = sum(w * (effect["effect"] - fixed_mean) ** 2 for w, effect in zip(fixed_weights, effects))
        df = len(effects) - 1
        sum_w = sum(fixed_weights)
        c = sum_w - sum(w * w for w in fixed_weights) / sum_w
        tau2 = max(0.0, (q - df) / c) if c > 0 else 0.0
        random_weights = [1.0 / (effect["variance"] + tau2) for effect in effects]
        pooled = sum(w * effect["effect"] for w, effect in zip(random_weights, effects)) / sum(random_weights)
        pooled_se = math.sqrt(1.0 / sum(random_weights))
        low = pooled - 1.96 * pooled_se
        high = pooled + 1.96 * pooled_se
        i2 = max(0.0, (q - df) / q * 100.0) if q > 0 else 0.0

        if i2 >= HETEROGENEITY_THRESHOLD:
            status = "heterogeneous"
            warnings.append("substantial_between_experiment_value_heterogeneity")
        elif low > 0:
            status = "positive"
        elif high < 0:
            status = "negative"
        else:
            status = "inconclusive"

        total_weight = sum(random_weights)
        rows = []
        for effect, weight in zip(effects, random_weights):
            rows.append(
                {
                    "experiment_id": effect["experiment_id"],
                    "campaign_id": effect["campaign_id"],
                    "campaign_title": effect["campaign_title"],
                    "treatment_units": effect["treatment_units"],
                    "holdout_units": effect["holdout_units"],
                    "treatment_mean_value": round(effect["treatment_mean_value"], 2),
                    "holdout_mean_value": round(effect["holdout_mean_value"], 2),
                    "incremental_value_per_unit": round(effect["effect"], 2),
                    "standard_error": round(math.sqrt(effect["variance"]), 2),
                    "weight_percent": round(weight / total_weight * 100.0, 2),
                }
            )
        rows.sort(key=lambda row: row["weight_percent"], reverse=True)

        return {
            "event_type": normalized_type,
            "value_unit": normalized_unit,
            "horizon_hours": horizon_hours,
            "aggregation": normalized_aggregation,
            "experiments_considered": len(experiment_rows),
            "experiments_included": len(effects),
            "randomized_units": sum(effect["treatment_units"] + effect["holdout_units"] for effect in effects),
            "pooled_incremental_value_per_unit": round(pooled, 2),
            "confidence_low_per_unit": round(low, 2),
            "confidence_high_per_unit": round(high, 2),
            "incremental_value_per_1000": round(pooled * 1000.0, 2),
            "tau_squared": round(tau2, 6),
            "i_squared_percent": round(i2, 2),
            "status": status,
            "warnings": warnings,
            "rows": rows,
        }

    @staticmethod
    def _sample_variance(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = fmean(values)
        return sum((value - mean) ** 2 for value in values) / (len(values) - 1)

    @classmethod
    def _insufficient(
        cls,
        event_type: str,
        value_unit: str,
        horizon_hours: int,
        aggregation: str,
        experiments_considered: int,
        effects: list[dict[str, Any]],
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "event_type": event_type,
            "value_unit": value_unit,
            "horizon_hours": horizon_hours,
            "aggregation": aggregation,
            "experiments_considered": experiments_considered,
            "experiments_included": len(effects),
            "randomized_units": sum(effect["treatment_units"] + effect["holdout_units"] for effect in effects),
            "pooled_incremental_value_per_unit": 0.0,
            "confidence_low_per_unit": 0.0,
            "confidence_high_per_unit": 0.0,
            "incremental_value_per_1000": 0.0,
            "tau_squared": 0.0,
            "i_squared_percent": 0.0,
            "status": "insufficient",
            "warnings": warnings,
            "rows": [
                {
                    "experiment_id": effect["experiment_id"],
                    "campaign_id": effect["campaign_id"],
                    "campaign_title": effect["campaign_title"],
                    "treatment_units": effect["treatment_units"],
                    "holdout_units": effect["holdout_units"],
                    "treatment_mean_value": round(effect["treatment_mean_value"], 2),
                    "holdout_mean_value": round(effect["holdout_mean_value"], 2),
                    "incremental_value_per_unit": round(effect["effect"], 2),
                    "standard_error": round(math.sqrt(effect["variance"]), 2),
                    "weight_percent": 0.0,
                }
                for effect in effects
            ],
        }

    @classmethod
    def _empty(cls, event_type: str, value_unit: str, horizon_hours: int, aggregation: str) -> dict[str, Any]:
        return cls._insufficient(
            event_type,
            value_unit,
            horizon_hours,
            aggregation,
            0,
            [],
            ["no_mature_randomized_value_experiments"],
        )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
