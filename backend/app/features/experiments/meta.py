from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
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
EVENT_QUERY_CHUNK = 4_000
HETEROGENEITY_THRESHOLD = 50.0


class IncrementalYieldMetaService:
    """Pool mature randomized risk differences with a random-effects model."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def analyze(
        self,
        *,
        owner_id: UUID,
        stage: str = "business",
        event_type: str = "converted",
        horizon_hours: int = 168,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        normalized_stage = stage.strip().lower()
        normalized_type = event_type.strip().lower().replace(" ", "_")
        if normalized_stage not in {"engagement", "business"}:
            raise ValueError("Incremental Yield supports engagement or business outcomes only")
        if not normalized_type:
            raise ValueError("event_type is required")
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
            return self._empty(normalized_stage, normalized_type, horizon_hours)

        experiment_by_id = {experiment.id: (experiment, campaign) for experiment, campaign in experiment_rows}
        experiment_ids = list(experiment_by_id)
        assignments_result = await self.session.execute(
            select(ExperimentAssignment)
            .where(
                ExperimentAssignment.owner_id == owner_id,
                ExperimentAssignment.experiment_id.in_(experiment_ids),
            )
            .order_by(ExperimentAssignment.assigned_at.desc())
            .limit(MAX_ASSIGNMENTS + 1)
        )
        all_assignments = list(assignments_result.scalars().all())
        assignments_capped = len(all_assignments) > MAX_ASSIGNMENTS
        assignments = all_assignments[:MAX_ASSIGNMENTS]

        by_experiment: dict[UUID, list[ExperimentAssignment]] = defaultdict(list)
        by_assignment_id = {}
        by_campaign_member = {}
        member_experiment_counts: dict[UUID, set[UUID]] = defaultdict(set)
        for assignment in assignments:
            by_experiment[assignment.experiment_id].append(assignment)
            by_assignment_id[assignment.id] = assignment
            by_campaign_member[(assignment.campaign_id, assignment.audience_member_id)] = assignment
            member_experiment_counts[assignment.audience_member_id].add(assignment.experiment_id)

        horizon = timedelta(hours=horizon_hours)
        positive_assignment_ids: set[UUID] = set()
        campaign_ids = [campaign.id for _experiment, campaign in experiment_rows]
        if campaign_ids:
            events_result = await self.session.execute(
                select(OutcomeEvent).where(
                    OutcomeEvent.owner_id == owner_id,
                    OutcomeEvent.campaign_id.in_(campaign_ids),
                    OutcomeEvent.stage == normalized_stage,
                    OutcomeEvent.event_type == normalized_type,
                    OutcomeEvent.success.is_(True),
                    OutcomeEvent.confidence >= min_confidence,
                )
            )
            for event in events_result.scalars().all():
                assignment = None
                if event.experiment_assignment_id is not None:
                    assignment = by_assignment_id.get(event.experiment_assignment_id)
                if assignment is None:
                    assignment = by_campaign_member.get((event.campaign_id, event.audience_member_id))
                if assignment is None:
                    continue
                observed = self._aware(event.observed_at)
                assigned = self._aware(assignment.assigned_at)
                if assigned <= observed <= assigned + horizon:
                    positive_assignment_ids.add(assignment.id)

        effects: list[dict[str, Any]] = []
        for experiment_id, units in by_experiment.items():
            experiment, campaign = experiment_by_id[experiment_id]
            treatment = [item for item in units if item.variant == "treatment"]
            holdout = [item for item in units if item.variant == "holdout"]
            if len(treatment) < MIN_ARM_SIZE or len(holdout) < MIN_ARM_SIZE:
                continue
            treatment_positive = sum(item.id in positive_assignment_ids for item in treatment)
            holdout_positive = sum(item.id in positive_assignment_ids for item in holdout)
            treatment_rate = treatment_positive / len(treatment)
            holdout_rate = holdout_positive / len(holdout)
            effect = treatment_rate - holdout_rate
            # Jeffreys-smoothed arm rates avoid zero variance when an arm has 0/all events.
            smooth_t = (treatment_positive + 0.5) / (len(treatment) + 1.0)
            smooth_h = (holdout_positive + 0.5) / (len(holdout) + 1.0)
            variance = (
                smooth_t * (1.0 - smooth_t) / len(treatment)
                + smooth_h * (1.0 - smooth_h) / len(holdout)
            )
            variance = max(variance, 1e-12)
            effects.append(
                {
                    "experiment_id": experiment.id,
                    "campaign_id": campaign.id,
                    "campaign_title": campaign.title,
                    "treatment_units": len(treatment),
                    "treatment_positives": treatment_positive,
                    "holdout_units": len(holdout),
                    "holdout_positives": holdout_positive,
                    "effect": effect,
                    "variance": variance,
                }
            )

        repeated_people = sum(1 for experiment_ids_for_member in member_experiment_counts.values() if len(experiment_ids_for_member) > 1)
        unique_people = len(member_experiment_counts)
        randomized_units = len(assignments)
        warnings: list[str] = []
        if repeated_people:
            warnings.append("repeated_people_across_experiments")
        if assignments_capped:
            warnings.append("assignment_history_capped")
        if len(effects) < 2:
            warnings.append("fewer_than_two_mature_experiments")
            return {
                "stage": normalized_stage,
                "event_type": normalized_type,
                "horizon_hours": horizon_hours,
                "experiments_considered": len(experiment_rows),
                "experiments_included": len(effects),
                "randomized_units": randomized_units,
                "unique_people": unique_people,
                "repeated_people": repeated_people,
                "pooled_lift_percentage_points": 0.0,
                "confidence_low_percentage_points": 0.0,
                "confidence_high_percentage_points": 0.0,
                "incremental_outcomes_per_1000": 0.0,
                "tau_squared": 0.0,
                "i_squared_percent": 0.0,
                "q_statistic": 0.0,
                "status": "insufficient",
                "warnings": warnings,
                "rows": self._individual_rows(effects, None),
            }

        fixed_weights = [1.0 / row["variance"] for row in effects]
        fixed_mean = sum(weight * row["effect"] for weight, row in zip(fixed_weights, effects)) / sum(fixed_weights)
        q = sum(weight * (row["effect"] - fixed_mean) ** 2 for weight, row in zip(fixed_weights, effects))
        df = len(effects) - 1
        sum_w = sum(fixed_weights)
        c = sum_w - sum(weight * weight for weight in fixed_weights) / sum_w
        tau_squared = max(0.0, (q - df) / c) if c > 0 else 0.0
        random_weights = [1.0 / (row["variance"] + tau_squared) for row in effects]
        pooled = sum(weight * row["effect"] for weight, row in zip(random_weights, effects)) / sum(random_weights)
        pooled_se = math.sqrt(1.0 / sum(random_weights))
        low = pooled - 1.96 * pooled_se
        high = pooled + 1.96 * pooled_se
        i_squared = max(0.0, (q - df) / q * 100.0) if q > 0 else 0.0

        if i_squared >= HETEROGENEITY_THRESHOLD:
            status = "heterogeneous"
            warnings.append("substantial_between_experiment_heterogeneity")
        elif low > 0:
            status = "positive"
        elif high < 0:
            status = "negative"
        else:
            status = "inconclusive"

        total_random_weight = sum(random_weights)
        rows = self._individual_rows(effects, random_weights, total_random_weight)
        return {
            "stage": normalized_stage,
            "event_type": normalized_type,
            "horizon_hours": horizon_hours,
            "experiments_considered": len(experiment_rows),
            "experiments_included": len(effects),
            "randomized_units": randomized_units,
            "unique_people": unique_people,
            "repeated_people": repeated_people,
            "pooled_lift_percentage_points": round(pooled * 100.0, 3),
            "confidence_low_percentage_points": round(low * 100.0, 3),
            "confidence_high_percentage_points": round(high * 100.0, 3),
            "incremental_outcomes_per_1000": round(pooled * 1000.0, 2),
            "tau_squared": round(tau_squared, 8),
            "i_squared_percent": round(i_squared, 2),
            "q_statistic": round(q, 4),
            "status": status,
            "warnings": warnings,
            "rows": rows,
        }

    @staticmethod
    def _individual_rows(
        effects: list[dict[str, Any]],
        weights: list[float] | None,
        total_weight: float | None = None,
    ) -> list[dict[str, Any]]:
        rows = []
        for index, effect in enumerate(effects):
            weight_percent = 0.0
            if weights is not None and total_weight:
                weight_percent = weights[index] / total_weight * 100.0
            rows.append(
                {
                    "experiment_id": effect["experiment_id"],
                    "campaign_id": effect["campaign_id"],
                    "campaign_title": effect["campaign_title"],
                    "treatment_units": effect["treatment_units"],
                    "treatment_positives": effect["treatment_positives"],
                    "holdout_units": effect["holdout_units"],
                    "holdout_positives": effect["holdout_positives"],
                    "lift_percentage_points": round(effect["effect"] * 100.0, 3),
                    "standard_error_percentage_points": round(math.sqrt(effect["variance"]) * 100.0, 3),
                    "weight_percent": round(weight_percent, 2),
                }
            )
        rows.sort(key=lambda row: row["weight_percent"], reverse=True)
        return rows

    @staticmethod
    def _empty(stage: str, event_type: str, horizon_hours: int) -> dict[str, Any]:
        return {
            "stage": stage,
            "event_type": event_type,
            "horizon_hours": horizon_hours,
            "experiments_considered": 0,
            "experiments_included": 0,
            "randomized_units": 0,
            "unique_people": 0,
            "repeated_people": 0,
            "pooled_lift_percentage_points": 0.0,
            "confidence_low_percentage_points": 0.0,
            "confidence_high_percentage_points": 0.0,
            "incremental_outcomes_per_1000": 0.0,
            "tau_squared": 0.0,
            "i_squared_percent": 0.0,
            "q_statistic": 0.0,
            "status": "insufficient",
            "warnings": ["no_mature_randomized_experiments"],
            "rows": [],
        }

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
