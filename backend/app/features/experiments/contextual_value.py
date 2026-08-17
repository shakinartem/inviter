from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.experiments.models import CampaignExperiment, ExperimentAssignment
from app.features.experiments.value import IncrementalBusinessValueService
from app.features.learning.models import OutcomeEvent
from app.features.segments.models import CampaignAudienceMember, CampaignAudienceSource


READINESS_BUCKET_SIZE = 20
MIN_WITHIN_EXPERIMENT_ARM = 5
MIN_REPLICATED_ARM_TOTAL = 30
MAX_ASSIGNMENTS = 100_000
PRIOR_SD_FLOOR = 1.0
VARIANCE_FLOOR = 1e-9


class ContextualIncrementalBusinessValueService:
    """Estimate randomized business-value lift by frozen readiness × signal.

    We compute a treatment-minus-holdout continuous-value contrast inside each
    randomized experiment first, pool repeated strata second, then partially
    pool the subgroup estimate toward the global randomized value effect.
    """

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
        global_value: dict[str, Any] | None = None,
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

        global_result = global_value or await IncrementalBusinessValueService(self.session).analyze(
            owner_id=owner_id,
            event_type=normalized_type,
            value_unit=normalized_unit,
            horizon_hours=horizon_hours,
            aggregation=normalized_aggregation,
            min_confidence=min_confidence,
        )
        warnings = [
            "verified_webhook_value_only",
            "subgroup_value_analysis_exploratory_multiple_comparisons",
        ]
        if global_result["status"] == "insufficient":
            warnings.append("global_randomized_value_prior_insufficient")
            return self._empty(
                normalized_type,
                normalized_unit,
                horizon_hours,
                normalized_aggregation,
                global_result,
                warnings,
            )
        if global_result["status"] == "heterogeneous":
            warnings.append("heterogeneous_global_value_prior")

        mature_cutoff = datetime.now(timezone.utc) - timedelta(hours=horizon_hours)
        experiments_result = await self.session.execute(
            select(CampaignExperiment).where(
                CampaignExperiment.owner_id == owner_id,
                CampaignExperiment.status == "assigned",
                CampaignExperiment.assigned_at.is_not(None),
                CampaignExperiment.assigned_at <= mature_cutoff,
            )
        )
        experiments = list(experiments_result.scalars().all())
        if not experiments:
            return self._empty(
                normalized_type,
                normalized_unit,
                horizon_hours,
                normalized_aggregation,
                global_result,
                warnings,
            )
        experiment_by_id = {item.id: item for item in experiments}

        rows_result = await self.session.execute(
            select(ExperimentAssignment, CampaignAudienceMember)
            .join(
                CampaignAudienceSource,
                CampaignAudienceSource.campaign_id == ExperimentAssignment.campaign_id,
            )
            .join(
                CampaignAudienceMember,
                and_(
                    CampaignAudienceMember.campaign_source_id == CampaignAudienceSource.id,
                    CampaignAudienceMember.audience_member_id == ExperimentAssignment.audience_member_id,
                ),
            )
            .where(
                ExperimentAssignment.owner_id == owner_id,
                ExperimentAssignment.experiment_id.in_(list(experiment_by_id)),
            )
            .order_by(ExperimentAssignment.assigned_at.desc())
            .limit(MAX_ASSIGNMENTS + 1)
        )
        loaded = list(rows_result.all())
        capped = len(loaded) > MAX_ASSIGNMENTS
        loaded = loaded[:MAX_ASSIGNMENTS]
        if capped:
            warnings.append("contextual_value_assignment_history_capped")

        assignment_by_id: dict[UUID, ExperimentAssignment] = {}
        assignment_by_campaign_member: dict[tuple[UUID, UUID], ExperimentAssignment] = {}
        frozen_by_assignment: dict[UUID, CampaignAudienceMember] = {}
        loaded_count_by_experiment: dict[UUID, int] = defaultdict(int)
        for assignment, frozen in loaded:
            assignment_by_id[assignment.id] = assignment
            assignment_by_campaign_member[(assignment.campaign_id, assignment.audience_member_id)] = assignment
            frozen_by_assignment[assignment.id] = frozen
            loaded_count_by_experiment[assignment.experiment_id] += 1

        complete_experiment_ids = {
            experiment_id
            for experiment_id, count in loaded_count_by_experiment.items()
            if count == experiment_by_id[experiment_id].candidate_pool_size
        }
        if len(complete_experiment_ids) < len(loaded_count_by_experiment):
            warnings.append("partial_contextual_value_experiments_excluded")
        if not complete_experiment_ids:
            warnings.append("no_complete_contextual_value_experiments")
            return self._empty(
                normalized_type,
                normalized_unit,
                horizon_hours,
                normalized_aggregation,
                global_result,
                warnings,
            )

        values_by_assignment: dict[UUID, list[float]] = defaultdict(list)
        horizon = timedelta(hours=horizon_hours)
        campaign_ids = [experiment_by_id[experiment_id].campaign_id for experiment_id in complete_experiment_ids]
        earliest = min(
            self._aware(experiment_by_id[experiment_id].assigned_at)
            for experiment_id in complete_experiment_ids
            if experiment_by_id[experiment_id].assigned_at is not None
        )
        latest = max(
            self._aware(experiment_by_id[experiment_id].assigned_at) + horizon
            for experiment_id in complete_experiment_ids
            if experiment_by_id[experiment_id].assigned_at is not None
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
                assignment = assignment_by_id.get(event.experiment_assignment_id)
            if assignment is None:
                assignment = assignment_by_campaign_member.get((event.campaign_id, event.audience_member_id))
            if assignment is None or assignment.experiment_id not in complete_experiment_ids:
                continue
            observed = self._aware(event.observed_at)
            assigned = self._aware(assignment.assigned_at)
            if assigned <= observed <= assigned + horizon:
                values_by_assignment[assignment.id].append(float(event.value or 0.0))

        aggregated_value: dict[UUID, float] = {}
        for assignment_id, assignment in assignment_by_id.items():
            if assignment.experiment_id not in complete_experiment_ids:
                continue
            values = values_by_assignment.get(assignment_id, [])
            if not values:
                aggregated_value[assignment_id] = 0.0
            elif normalized_aggregation == "max":
                aggregated_value[assignment_id] = max(values)
            else:
                aggregated_value[assignment_id] = sum(values)

        units_by_cell: dict[tuple[UUID, int, str], list[ExperimentAssignment]] = defaultdict(list)
        for assignment_id, assignment in assignment_by_id.items():
            if assignment.experiment_id not in complete_experiment_ids:
                continue
            frozen = frozen_by_assignment[assignment_id]
            bucket = self._readiness_bucket(frozen.readiness_score)
            signal = frozen.strongest_signal_type or "no_intent_signal"
            units_by_cell[(assignment.experiment_id, bucket, signal)].append(assignment)

        contrasts_by_stratum: dict[tuple[int, str], list[dict[str, float]]] = defaultdict(list)
        totals_by_stratum: dict[tuple[int, str], dict[str, Any]] = defaultdict(
            lambda: {
                "treatment_units": 0,
                "holdout_units": 0,
                "treatment_values": [],
                "holdout_values": [],
            }
        )
        for (_experiment_id, bucket, signal), units in units_by_cell.items():
            treatment_units = [item for item in units if item.variant == "treatment"]
            holdout_units = [item for item in units if item.variant == "holdout"]
            if len(treatment_units) < MIN_WITHIN_EXPERIMENT_ARM or len(holdout_units) < MIN_WITHIN_EXPERIMENT_ARM:
                continue
            treatment_values = [aggregated_value[item.id] for item in treatment_units]
            holdout_values = [aggregated_value[item.id] for item in holdout_units]
            t_mean = fmean(treatment_values)
            h_mean = fmean(holdout_values)
            variance = max(
                self._sample_variance(treatment_values) / len(treatment_values)
                + self._sample_variance(holdout_values) / len(holdout_values),
                VARIANCE_FLOOR,
            )
            key = (bucket, signal)
            contrasts_by_stratum[key].append({"effect": t_mean - h_mean, "variance": variance})
            totals = totals_by_stratum[key]
            totals["treatment_units"] += len(treatment_values)
            totals["holdout_units"] += len(holdout_values)
            totals["treatment_values"].extend(treatment_values)
            totals["holdout_values"].extend(holdout_values)

        global_effect = float(global_result["pooled_incremental_value_per_unit"])
        global_low = float(global_result["confidence_low_per_unit"])
        global_high = float(global_result["confidence_high_per_unit"])
        global_se = max((global_high - global_low) / (2.0 * 1.96), 1e-6)
        prior_variance = max(
            global_se * global_se + float(global_result["tau_squared"]),
            PRIOR_SD_FLOOR * PRIOR_SD_FLOOR,
        )

        output_rows: list[dict[str, Any]] = []
        for (bucket, signal), contrasts in contrasts_by_stratum.items():
            pooled_effect, pooled_variance = self._pool_within_stratum(contrasts)
            if pooled_variance <= 0:
                continue
            shrunk, data_weight = self.shrink_effect(
                contextual_effect=pooled_effect,
                contextual_variance=pooled_variance,
                global_effect=global_effect,
                prior_variance=prior_variance,
            )
            posterior_variance = 1.0 / (1.0 / pooled_variance + 1.0 / prior_variance)
            posterior_se = math.sqrt(posterior_variance)
            low = shrunk - 1.96 * posterior_se
            high = shrunk + 1.96 * posterior_se
            totals = totals_by_stratum[(bucket, signal)]
            experiments_count = len(contrasts)
            replicated = (
                experiments_count >= 2
                and totals["treatment_units"] >= MIN_REPLICATED_ARM_TOTAL
                and totals["holdout_units"] >= MIN_REPLICATED_ARM_TOTAL
            )
            evidence_status = "replicated" if replicated else "exploratory"
            if replicated and low > 0:
                direction = "positive"
            elif replicated and high < 0:
                direction = "negative"
            else:
                direction = "inconclusive"
            output_rows.append(
                {
                    "readiness_bucket": self._bucket_label(bucket),
                    "strongest_signal_type": signal,
                    "experiments": experiments_count,
                    "treatment_units": totals["treatment_units"],
                    "holdout_units": totals["holdout_units"],
                    "treatment_mean_value": round(fmean(totals["treatment_values"]), 2),
                    "holdout_mean_value": round(fmean(totals["holdout_values"]), 2),
                    "raw_incremental_value_per_unit": round(pooled_effect, 2),
                    "shrunk_incremental_value_per_unit": round(shrunk, 2),
                    "confidence_low_per_unit": round(low, 2),
                    "confidence_high_per_unit": round(high, 2),
                    "data_weight_percent": round(data_weight * 100.0, 2),
                    "incremental_value_per_1000": round(shrunk * 1000.0, 2),
                    "evidence_status": evidence_status,
                    "direction": direction,
                }
            )

        output_rows.sort(
            key=lambda row: (
                row["evidence_status"] == "replicated",
                row["data_weight_percent"],
                abs(row["shrunk_incremental_value_per_unit"]),
            ),
            reverse=True,
        )
        replicated_count = sum(row["evidence_status"] == "replicated" for row in output_rows)
        if not output_rows:
            warnings.append("no_contextual_value_strata_with_both_randomized_arms")
        if output_rows and not replicated_count:
            warnings.append("contextual_value_evidence_not_replicated")

        return {
            "event_type": normalized_type,
            "value_unit": normalized_unit,
            "horizon_hours": horizon_hours,
            "aggregation": normalized_aggregation,
            "global_prior_value_per_unit": global_result["pooled_incremental_value_per_unit"],
            "global_prior_status": global_result["status"],
            "global_prior_i_squared_percent": global_result["i_squared_percent"],
            "strata_evaluated": len(output_rows),
            "strata_replicated": replicated_count,
            "warnings": warnings,
            "rows": output_rows[:100],
        }

    @staticmethod
    def _pool_within_stratum(contrasts: list[dict[str, float]]) -> tuple[float, float]:
        if len(contrasts) == 1:
            return contrasts[0]["effect"], contrasts[0]["variance"]
        fixed_weights = [1.0 / row["variance"] for row in contrasts]
        fixed_mean = sum(weight * row["effect"] for weight, row in zip(fixed_weights, contrasts)) / sum(fixed_weights)
        q = sum(weight * (row["effect"] - fixed_mean) ** 2 for weight, row in zip(fixed_weights, contrasts))
        df = len(contrasts) - 1
        sum_w = sum(fixed_weights)
        c = sum_w - sum(weight * weight for weight in fixed_weights) / sum_w
        tau2 = max(0.0, (q - df) / c) if c > 0 else 0.0
        weights = [1.0 / (row["variance"] + tau2) for row in contrasts]
        pooled = sum(weight * row["effect"] for weight, row in zip(weights, contrasts)) / sum(weights)
        return pooled, 1.0 / sum(weights)

    @staticmethod
    def shrink_effect(
        *,
        contextual_effect: float,
        contextual_variance: float,
        global_effect: float,
        prior_variance: float,
    ) -> tuple[float, float]:
        data_weight = prior_variance / (prior_variance + contextual_variance)
        posterior = data_weight * contextual_effect + (1.0 - data_weight) * global_effect
        return posterior, data_weight

    @staticmethod
    def _sample_variance(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = fmean(values)
        return sum((value - mean) ** 2 for value in values) / (len(values) - 1)

    @staticmethod
    def _readiness_bucket(value: float | None) -> int:
        score = max(0.0, min(float(value or 0.0), 100.0))
        return min(int(score // READINESS_BUCKET_SIZE) * READINESS_BUCKET_SIZE, 80)

    @staticmethod
    def _bucket_label(start: int) -> str:
        return f"{start}-{100 if start == 80 else start + READINESS_BUCKET_SIZE - 1}"

    @staticmethod
    def _empty(
        event_type: str,
        value_unit: str,
        horizon_hours: int,
        aggregation: str,
        global_result: dict[str, Any],
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "event_type": event_type,
            "value_unit": value_unit,
            "horizon_hours": horizon_hours,
            "aggregation": aggregation,
            "global_prior_value_per_unit": global_result.get("pooled_incremental_value_per_unit", 0.0),
            "global_prior_status": global_result.get("status", "insufficient"),
            "global_prior_i_squared_percent": global_result.get("i_squared_percent", 0.0),
            "strata_evaluated": 0,
            "strata_replicated": 0,
            "warnings": warnings,
            "rows": [],
        }

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
