from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.experiments.meta import IncrementalYieldMetaService
from app.features.experiments.models import CampaignExperiment, ExperimentAssignment
from app.features.learning.models import OutcomeEvent
from app.features.segments.models import CampaignAudienceMember, CampaignAudienceSource


READINESS_BUCKET_SIZE = 20
MIN_WITHIN_EXPERIMENT_ARM = 5
MIN_REPLICATED_ARM_TOTAL = 30
MAX_ASSIGNMENTS = 100_000
PRIOR_SD_FLOOR = 0.01


class ContextualIncrementalYieldService:
    """Estimate randomized lift by frozen readiness × intent-signal context.

    Every contextual contrast is computed within one randomized experiment first,
    then pooled across experiments. Sparse strata are partially pooled toward the
    global randomized effect to reduce subgroup overfitting.
    """

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
            raise ValueError("Contextual Incremental Yield supports engagement or business outcomes only")
        if not normalized_type:
            raise ValueError("event_type is required")
        if horizon_hours < 1 or horizon_hours > 2160:
            raise ValueError("horizon_hours must be between 1 and 2160")
        if min_confidence < 0 or min_confidence > 1:
            raise ValueError("min_confidence must be between 0 and 1")

        global_meta = await IncrementalYieldMetaService(self.session).analyze(
            owner_id=owner_id,
            stage=normalized_stage,
            event_type=normalized_type,
            horizon_hours=horizon_hours,
            min_confidence=min_confidence,
        )
        warnings = ["subgroup_analysis_exploratory_multiple_comparisons"]
        if global_meta["status"] == "insufficient":
            warnings.append("global_randomized_prior_insufficient")
            return self._empty(normalized_stage, normalized_type, horizon_hours, global_meta, warnings)
        if global_meta["status"] == "heterogeneous":
            warnings.append("heterogeneous_global_prior")

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
            return self._empty(normalized_stage, normalized_type, horizon_hours, global_meta, warnings)
        experiment_by_id = {item.id: item for item in experiments}
        campaign_ids = [item.campaign_id for item in experiments]

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
            warnings.append("contextual_assignment_history_capped")

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
            warnings.append("partial_contextual_experiments_excluded")

        horizon = timedelta(hours=horizon_hours)
        positive_assignment_ids: set[UUID] = set()
        complete_campaign_ids = [
            experiment_by_id[experiment_id].campaign_id for experiment_id in complete_experiment_ids
        ]
        if complete_campaign_ids:
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
                    OutcomeEvent.campaign_id.in_(complete_campaign_ids),
                    OutcomeEvent.stage == normalized_stage,
                    OutcomeEvent.event_type == normalized_type,
                    OutcomeEvent.success.is_(True),
                    OutcomeEvent.confidence >= min_confidence,
                    OutcomeEvent.observed_at >= earliest,
                    OutcomeEvent.observed_at <= latest,
                )
            )
            for event in events_result.scalars().all():
                assignment = None
                if event.experiment_assignment_id is not None:
                    assignment = assignment_by_id.get(event.experiment_assignment_id)
                if assignment is None:
                    assignment = assignment_by_campaign_member.get(
                        (event.campaign_id, event.audience_member_id)
                    )
                if assignment is None or assignment.experiment_id not in complete_experiment_ids:
                    continue
                observed = self._aware(event.observed_at)
                assigned = self._aware(assignment.assigned_at)
                if assigned <= observed <= assigned + horizon:
                    positive_assignment_ids.add(assignment.id)

        # First build randomized contrasts within each experiment/stratum.
        units_by_cell: dict[tuple[UUID, int, str], list[ExperimentAssignment]] = defaultdict(list)
        for assignment_id, assignment in assignment_by_id.items():
            if assignment.experiment_id not in complete_experiment_ids:
                continue
            frozen = frozen_by_assignment[assignment_id]
            bucket = self._readiness_bucket(frozen.readiness_score)
            signal = frozen.strongest_signal_type or "no_intent_signal"
            units_by_cell[(assignment.experiment_id, bucket, signal)].append(assignment)

        contrasts_by_stratum: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
        totals_by_stratum: dict[tuple[int, str], dict[str, int]] = defaultdict(
            lambda: {
                "treatment_units": 0,
                "treatment_positives": 0,
                "holdout_units": 0,
                "holdout_positives": 0,
            }
        )
        for (_experiment_id, bucket, signal), units in units_by_cell.items():
            treatment = [item for item in units if item.variant == "treatment"]
            holdout = [item for item in units if item.variant == "holdout"]
            if len(treatment) < MIN_WITHIN_EXPERIMENT_ARM or len(holdout) < MIN_WITHIN_EXPERIMENT_ARM:
                continue
            t_pos = sum(item.id in positive_assignment_ids for item in treatment)
            h_pos = sum(item.id in positive_assignment_ids for item in holdout)
            t_rate = t_pos / len(treatment)
            h_rate = h_pos / len(holdout)
            smooth_t = (t_pos + 0.5) / (len(treatment) + 1.0)
            smooth_h = (h_pos + 0.5) / (len(holdout) + 1.0)
            variance = max(
                smooth_t * (1.0 - smooth_t) / len(treatment)
                + smooth_h * (1.0 - smooth_h) / len(holdout),
                1e-12,
            )
            key = (bucket, signal)
            contrasts_by_stratum[key].append({"effect": t_rate - h_rate, "variance": variance})
            totals = totals_by_stratum[key]
            totals["treatment_units"] += len(treatment)
            totals["treatment_positives"] += t_pos
            totals["holdout_units"] += len(holdout)
            totals["holdout_positives"] += h_pos

        global_effect = float(global_meta["pooled_lift_percentage_points"]) / 100.0
        global_low = float(global_meta["confidence_low_percentage_points"]) / 100.0
        global_high = float(global_meta["confidence_high_percentage_points"]) / 100.0
        global_se = max((global_high - global_low) / (2.0 * 1.96), 1e-6)
        prior_variance = max(
            global_se * global_se + float(global_meta["tau_squared"]),
            PRIOR_SD_FLOOR * PRIOR_SD_FLOOR,
        )

        output_rows: list[dict[str, Any]] = []
        for (bucket, signal), contrasts in contrasts_by_stratum.items():
            pooled_effect, pooled_variance = self._pool_within_stratum(contrasts)
            if pooled_variance <= 0:
                continue
            data_weight = prior_variance / (prior_variance + pooled_variance)
            shrunk = data_weight * pooled_effect + (1.0 - data_weight) * global_effect
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
                    **totals,
                    "raw_lift_percentage_points": round(pooled_effect * 100.0, 3),
                    "shrunk_lift_percentage_points": round(shrunk * 100.0, 3),
                    "confidence_low_percentage_points": round(low * 100.0, 3),
                    "confidence_high_percentage_points": round(high * 100.0, 3),
                    "data_weight_percent": round(data_weight * 100.0, 2),
                    "incremental_outcomes_per_1000": round(shrunk * 1000.0, 2),
                    "evidence_status": evidence_status,
                    "direction": direction,
                }
            )

        output_rows.sort(
            key=lambda row: (
                row["evidence_status"] == "replicated",
                row["data_weight_percent"],
                abs(row["shrunk_lift_percentage_points"]),
            ),
            reverse=True,
        )
        replicated_count = sum(row["evidence_status"] == "replicated" for row in output_rows)
        if not output_rows:
            warnings.append("no_contextual_strata_with_both_randomized_arms")
        if output_rows and not replicated_count:
            warnings.append("contextual_evidence_not_replicated")

        return {
            "stage": normalized_stage,
            "event_type": normalized_type,
            "horizon_hours": horizon_hours,
            "global_prior_lift_percentage_points": global_meta["pooled_lift_percentage_points"],
            "global_prior_status": global_meta["status"],
            "global_prior_i_squared_percent": global_meta["i_squared_percent"],
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
        fixed_mean = sum(
            weight * row["effect"] for weight, row in zip(fixed_weights, contrasts)
        ) / sum(fixed_weights)
        q = sum(
            weight * (row["effect"] - fixed_mean) ** 2
            for weight, row in zip(fixed_weights, contrasts)
        )
        df = len(contrasts) - 1
        sum_w = sum(fixed_weights)
        c = sum_w - sum(weight * weight for weight in fixed_weights) / sum_w
        tau2 = max(0.0, (q - df) / c) if c > 0 else 0.0
        weights = [1.0 / (row["variance"] + tau2) for row in contrasts]
        pooled = sum(weight * row["effect"] for weight, row in zip(weights, contrasts)) / sum(weights)
        variance = 1.0 / sum(weights)
        return pooled, variance

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
    def _readiness_bucket(value: float | None) -> int:
        score = max(0.0, min(float(value or 0.0), 100.0))
        return min(int(score // READINESS_BUCKET_SIZE) * READINESS_BUCKET_SIZE, 80)

    @staticmethod
    def _bucket_label(start: int) -> str:
        return f"{start}-{100 if start == 80 else start + READINESS_BUCKET_SIZE - 1}"

    @staticmethod
    def _empty(
        stage: str,
        event_type: str,
        horizon_hours: int,
        global_meta: dict[str, Any],
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "stage": stage,
            "event_type": event_type,
            "horizon_hours": horizon_hours,
            "global_prior_lift_percentage_points": global_meta.get("pooled_lift_percentage_points", 0.0),
            "global_prior_status": global_meta.get("status", "insufficient"),
            "global_prior_i_squared_percent": global_meta.get("i_squared_percent", 0.0),
            "strata_evaluated": 0,
            "strata_replicated": 0,
            "warnings": warnings,
            "rows": [],
        }

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
