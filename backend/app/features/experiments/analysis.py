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
from app.features.orchestration.models import ActionJob
from app.features.segments.models import CampaignAudienceMember, CampaignAudienceSource


MIN_ARM_SIZE = 30
BALANCE_WARNING_THRESHOLD = 0.25


class CausalLiftService:
    """Estimate intention-to-treat lift for one randomized campaign experiment."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def campaign_lift(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        stage: str = "business",
        event_type: str = "converted",
        horizon_hours: int = 168,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        normalized_stage = stage.strip().lower()
        normalized_type = event_type.strip().lower().replace(" ", "_")
        if normalized_stage not in {"engagement", "business"}:
            raise ValueError("Causal lift supports engagement or business outcomes only")
        if not normalized_type:
            raise ValueError("event_type is required")
        if horizon_hours < 1 or horizon_hours > 2160:
            raise ValueError("horizon_hours must be between 1 and 2160")
        if min_confidence < 0 or min_confidence > 1:
            raise ValueError("min_confidence must be between 0 and 1")

        experiment_result = await self.session.execute(
            select(CampaignExperiment, InviteCampaign)
            .join(InviteCampaign, InviteCampaign.id == CampaignExperiment.campaign_id)
            .where(
                CampaignExperiment.owner_id == owner_id,
                CampaignExperiment.campaign_id == campaign_id,
            )
        )
        row = experiment_result.one_or_none()
        if row is None:
            raise ValueError("Randomized campaign experiment not found")
        experiment, campaign = row
        if experiment.status != "assigned" or experiment.assigned_at is None:
            raise ValueError("Experiment has not been randomized yet")

        assignments_result = await self.session.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == experiment.id,
                ExperimentAssignment.owner_id == owner_id,
            )
        )
        assignments = list(assignments_result.scalars().all())
        if not assignments:
            raise ValueError("Experiment has no randomized assignments")

        assigned_at = self._aware(experiment.assigned_at)
        horizon = timedelta(hours=horizon_hours)
        horizon_end = assigned_at + horizon
        now = datetime.now(timezone.utc)
        mature = now >= horizon_end
        hours_until_mature = max((horizon_end - now).total_seconds() / 3600.0, 0.0)

        assignment_by_id = {item.id: item for item in assignments}
        assignment_by_member = {item.audience_member_id: item for item in assignments}

        events_result = await self.session.execute(
            select(OutcomeEvent).where(
                OutcomeEvent.owner_id == owner_id,
                OutcomeEvent.campaign_id == campaign_id,
                OutcomeEvent.stage == normalized_stage,
                OutcomeEvent.event_type == normalized_type,
                OutcomeEvent.success.is_(True),
                OutcomeEvent.confidence >= min_confidence,
                OutcomeEvent.observed_at >= assigned_at,
                OutcomeEvent.observed_at <= horizon_end,
            )
        )
        positive_assignment_ids: set[UUID] = set()
        for event in events_result.scalars().all():
            assignment = None
            if event.experiment_assignment_id is not None:
                assignment = assignment_by_id.get(event.experiment_assignment_id)
            if assignment is None:
                assignment = assignment_by_member.get(event.audience_member_id)
            if assignment is not None:
                positive_assignment_ids.add(assignment.id)

        treatment_assignments = [item for item in assignments if item.variant == "treatment"]
        holdout_assignments = [item for item in assignments if item.variant == "holdout"]
        treatment = self._arm_result(treatment_assignments, positive_assignment_ids, "treatment")
        holdout = self._arm_result(holdout_assignments, positive_assignment_ids, "holdout")

        lift = treatment["rate_fraction"] - holdout["rate_fraction"]
        # Newcombe-style conservative interval from independent Wilson arm intervals.
        diff_low = treatment["low_fraction"] - holdout["high_fraction"]
        diff_high = treatment["high_fraction"] - holdout["low_fraction"]
        relative_lift = None
        if holdout["rate_fraction"] > 0:
            relative_lift = lift / holdout["rate_fraction"] * 100.0

        execution_rate, transport_success_rate = await self._execution_diagnostics(
            owner_id=owner_id,
            campaign_id=campaign_id,
            treatment_assignments=treatment_assignments,
        )
        balance = await self._balance_metrics(
            owner_id=owner_id,
            campaign_id=campaign_id,
            assignments=assignments,
        )

        warnings: list[str] = []
        if not mature:
            warnings.append("observation_horizon_not_mature")
        if len(treatment_assignments) < MIN_ARM_SIZE or len(holdout_assignments) < MIN_ARM_SIZE:
            warnings.append("small_randomized_arms")
        if execution_rate < 90.0:
            warnings.append("treatment_execution_dilution")
        if any(
            metric["standardized_difference"] is not None
            and abs(float(metric["standardized_difference"])) > BALANCE_WARNING_THRESHOLD
            for metric in balance
        ):
            warnings.append("randomization_balance_warning")

        if not mature or len(treatment_assignments) < MIN_ARM_SIZE or len(holdout_assignments) < MIN_ARM_SIZE:
            status = "insufficient"
        elif diff_low > 0:
            status = "positive"
        elif diff_high < 0:
            status = "negative"
        else:
            status = "inconclusive"

        return {
            "experiment_id": experiment.id,
            "campaign_id": campaign.id,
            "campaign_title": campaign.title,
            "holdout_percentage": experiment.holdout_percentage,
            "stage": normalized_stage,
            "event_type": normalized_type,
            "horizon_hours": horizon_hours,
            "mature": mature,
            "hours_until_mature": round(hours_until_mature, 2),
            "status": status,
            "treatment": self._public_arm(treatment),
            "holdout": self._public_arm(holdout),
            "lift_percentage_points": round(lift * 100.0, 2),
            "confidence_low_percentage_points": round(diff_low * 100.0, 2),
            "confidence_high_percentage_points": round(diff_high * 100.0, 2),
            "relative_lift_percent": round(relative_lift, 2) if relative_lift is not None else None,
            "incremental_outcomes_per_1000": round(lift * 1000.0, 2),
            "treatment_execution_rate": round(execution_rate, 2),
            "treatment_transport_success_rate": round(transport_success_rate, 2),
            "balance": balance,
            "warnings": warnings,
        }

    async def _execution_diagnostics(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        treatment_assignments: list[ExperimentAssignment],
    ) -> tuple[float, float]:
        denominator = len(treatment_assignments)
        if denominator == 0:
            return 0.0, 0.0
        treatment_member_ids = {item.audience_member_id for item in treatment_assignments}
        jobs_result = await self.session.execute(
            select(ActionJob).where(
                ActionJob.owner_id == owner_id,
                ActionJob.campaign_id == campaign_id,
                ActionJob.audience_member_id.in_(treatment_member_ids),
            )
        )
        jobs = list(jobs_result.scalars().all())
        executed_members = {job.audience_member_id for job in jobs if job.attempts > 0}
        job_by_id = {job.id: job for job in jobs}

        successful_result = await self.session.execute(
            select(OutcomeEvent.action_job_id).where(
                OutcomeEvent.owner_id == owner_id,
                OutcomeEvent.campaign_id == campaign_id,
                OutcomeEvent.stage == "transport",
                OutcomeEvent.success.is_(True),
                OutcomeEvent.action_job_id.in_(list(job_by_id)),
            )
        )
        successful_members = {
            job_by_id[job_id].audience_member_id
            for job_id in successful_result.scalars().all()
            if job_id in job_by_id
        }
        return (
            len(executed_members) / denominator * 100.0,
            len(successful_members) / denominator * 100.0,
        )

    async def _balance_metrics(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        assignments: list[ExperimentAssignment],
    ) -> list[dict[str, Any]]:
        source_result = await self.session.execute(
            select(CampaignAudienceSource).where(
                CampaignAudienceSource.owner_id == owner_id,
                CampaignAudienceSource.campaign_id == campaign_id,
            )
        )
        source = source_result.scalar_one_or_none()
        if source is None:
            return []
        member_ids = [item.audience_member_id for item in assignments]
        frozen_result = await self.session.execute(
            select(CampaignAudienceMember).where(
                CampaignAudienceMember.campaign_source_id == source.id,
                CampaignAudienceMember.audience_member_id.in_(member_ids),
            )
        )
        frozen = {item.audience_member_id: item for item in frozen_result.scalars().all()}
        variant_by_member = {item.audience_member_id: item.variant for item in assignments}

        metrics: list[dict[str, Any]] = []
        for name in ("activity_score", "intent_score", "readiness_score"):
            treatment_values: list[float] = []
            holdout_values: list[float] = []
            for member_id, row in frozen.items():
                value = getattr(row, name)
                if value is None:
                    continue
                target = treatment_values if variant_by_member.get(member_id) == "treatment" else holdout_values
                target.append(float(value))
            treatment_mean = fmean(treatment_values) if treatment_values else None
            holdout_mean = fmean(holdout_values) if holdout_values else None
            smd = self._standardized_difference(treatment_values, holdout_values)
            metrics.append(
                {
                    "metric": name,
                    "treatment_mean": round(treatment_mean, 2) if treatment_mean is not None else None,
                    "holdout_mean": round(holdout_mean, 2) if holdout_mean is not None else None,
                    "standardized_difference": round(smd, 3) if smd is not None else None,
                }
            )
        return metrics

    @classmethod
    def _arm_result(
        cls,
        assignments: list[ExperimentAssignment],
        positive_assignment_ids: set[UUID],
        variant: str,
    ) -> dict[str, Any]:
        units = len(assignments)
        positives = sum(1 for item in assignments if item.id in positive_assignment_ids)
        rate = positives / units if units else 0.0
        low, high = cls._wilson_interval(positives, units)
        return {
            "variant": variant,
            "units": units,
            "positives": positives,
            "rate_fraction": rate,
            "low_fraction": low,
            "high_fraction": high,
        }

    @staticmethod
    def _public_arm(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "variant": row["variant"],
            "units": row["units"],
            "positives": row["positives"],
            "rate": round(row["rate_fraction"] * 100.0, 2),
            "confidence_low": round(row["low_fraction"] * 100.0, 2),
            "confidence_high": round(row["high_fraction"] * 100.0, 2),
        }

    @staticmethod
    def _wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
        if total <= 0:
            return 0.0, 0.0
        p = successes / total
        denominator = 1.0 + z * z / total
        center = (p + z * z / (2.0 * total)) / denominator
        margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total) / denominator
        return max(0.0, center - margin), min(1.0, center + margin)

    @staticmethod
    def _standardized_difference(a: list[float], b: list[float]) -> float | None:
        if len(a) < 2 or len(b) < 2:
            return None
        mean_a = fmean(a)
        mean_b = fmean(b)
        var_a = sum((value - mean_a) ** 2 for value in a) / (len(a) - 1)
        var_b = sum((value - mean_b) ** 2 for value in b) / (len(b) - 1)
        pooled_sd = math.sqrt((var_a + var_b) / 2.0)
        if pooled_sd == 0:
            return 0.0 if mean_a == mean_b else None
        return (mean_a - mean_b) / pooled_sd

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
