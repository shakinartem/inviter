from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.orchestration.sla import MODEL_VERSION
from app.features.orchestration.sla_calibration import calibration_metrics
from app.features.orchestration.sla_governance_models import ExecutionSLACalibrator
from app.features.orchestration.sla_governance_schemas import (
    SLALiveMonitorBucket,
    SLALiveMonitorResponse,
)
from app.features.orchestration.sla_models import ExecutionSLAForecastSnapshot


MIN_REVALIDATION_SAMPLES = 50


def snapshot_probabilities(snapshot: ExecutionSLAForecastSnapshot) -> tuple[float, float] | None:
    scenarios = snapshot.scenarios_snapshot or []
    if not isinstance(scenarios, list) or not scenarios:
        return None
    reserve = float(snapshot.current_reserve_percentage or 0.0)
    candidates = [item for item in scenarios if isinstance(item, dict)]
    if not candidates:
        return None
    current = min(candidates, key=lambda item: abs(float(item.get("reserve_percentage", 0.0)) - reserve))
    raw = current.get("modelled_workload_completion_probability")
    calibrated = current.get("calibrated_workload_completion_probability")
    if raw is None or calibrated is None:
        return None
    return (
        min(max(float(raw), 0.0), 1.0),
        min(max(float(calibrated), 0.0), 1.0),
    )


def live_status(
    *,
    samples: int,
    raw_brier: float | None,
    calibrated_brier: float | None,
    raw_ece: float | None,
    calibrated_ece: float | None,
    raw_bias: float | None,
    calibrated_bias: float | None,
    holdout_calibrated_brier: float | None,
    holdout_calibrated_ece: float | None,
) -> tuple[str, bool]:
    if samples < 20:
        return "insufficient", False
    if samples < MIN_REVALIDATION_SAMPLES:
        return "watch", False
    assert raw_brier is not None and calibrated_brier is not None
    assert raw_ece is not None and calibrated_ece is not None
    assert raw_bias is not None and calibrated_bias is not None

    materially_worse_than_raw = (
        calibrated_brier > raw_brier + 0.02
        or calibrated_ece > raw_ece + 0.05
        or abs(calibrated_bias) > abs(raw_bias) + 0.05
    )
    materially_worse_than_holdout = (
        (holdout_calibrated_brier is not None and calibrated_brier > holdout_calibrated_brier + 0.05)
        or (holdout_calibrated_ece is not None and calibrated_ece > holdout_calibrated_ece + 0.08)
    )
    if materially_worse_than_raw or materially_worse_than_holdout:
        return "revalidation_required", True

    if calibrated_brier <= raw_brier + 0.005 and calibrated_ece <= raw_ece + 0.02:
        return "healthy", False
    return "watch", False


class ExecutionSLALiveMonitoringService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def evaluate(
        self,
        *,
        owner_id: UUID,
        base_model_version: str = MODEL_VERSION,
        limit: int = 5000,
    ) -> SLALiveMonitorResponse:
        active = (
            await self.session.execute(
                select(ExecutionSLACalibrator)
                .where(
                    ExecutionSLACalibrator.owner_id == owner_id,
                    ExecutionSLACalibrator.base_model_version == base_model_version,
                    ExecutionSLACalibrator.status == "active",
                )
                .order_by(ExecutionSLACalibrator.activated_at.desc().nullslast())
                .limit(1)
            )
        ).scalar_one_or_none()
        if active is None or active.activated_at is None:
            return SLALiveMonitorResponse(
                base_model_version=base_model_version,
                active_calibrator_id=None,
                active_calibrator_version=None,
                activated_at=None,
                post_activation_labels=0,
                minimum_revalidation_samples=MIN_REVALIDATION_SAMPLES,
                raw_brier=None,
                calibrated_brier=None,
                raw_ece=None,
                calibrated_ece=None,
                raw_bias=None,
                calibrated_bias=None,
                holdout_calibrated_brier=None,
                holdout_calibrated_ece=None,
                status="raw_only",
                retirement_recommended=False,
                warnings=["No active SLA calibrator. Forecasts use raw execution-sla-v1 completion probability."],
                buckets=[],
            )

        result = await self.session.execute(
            select(ExecutionSLAForecastSnapshot)
            .where(
                ExecutionSLAForecastSnapshot.owner_id == owner_id,
                ExecutionSLAForecastSnapshot.model_version == base_model_version,
                ExecutionSLAForecastSnapshot.label_status == "labeled",
                ExecutionSLAForecastSnapshot.actual_met_sla.is_not(None),
                ExecutionSLAForecastSnapshot.created_at >= active.activated_at,
            )
            .order_by(ExecutionSLAForecastSnapshot.created_at.asc())
            .limit(max(1, min(int(limit), 10000)))
        )
        rows = list(result.scalars().all())

        raw_predictions: list[float] = []
        calibrated_predictions: list[float] = []
        outcomes: list[int] = []
        skipped_wrong_version = 0
        skipped_missing_probability = 0
        for row in rows:
            snapshot_version = (row.input_snapshot or {}).get("active_calibrator_version")
            if snapshot_version != active.calibrator_version:
                skipped_wrong_version += 1
                continue
            probabilities = snapshot_probabilities(row)
            if probabilities is None:
                skipped_missing_probability += 1
                continue
            raw, calibrated = probabilities
            raw_predictions.append(raw)
            calibrated_predictions.append(calibrated)
            outcomes.append(1 if row.actual_met_sla else 0)

        raw_metrics = calibration_metrics(raw_predictions, outcomes)
        calibrated_metrics = calibration_metrics(calibrated_predictions, outcomes)
        samples = len(outcomes)
        status, retirement = live_status(
            samples=samples,
            raw_brier=raw_metrics["brier_score"],
            calibrated_brier=calibrated_metrics["brier_score"],
            raw_ece=raw_metrics["expected_calibration_error"],
            calibrated_ece=calibrated_metrics["expected_calibration_error"],
            raw_bias=raw_metrics["calibration_bias"],
            calibrated_bias=calibrated_metrics["calibration_bias"],
            holdout_calibrated_brier=float(active.calibrated_brier_test),
            holdout_calibrated_ece=float(active.calibrated_ece_test),
        )

        warnings = [
            "Live monitoring uses only post-activation, intervention-clean, queue-valid labeled forecasts produced by the active calibrator version.",
            "Retirement is recommendation-only; the monitor never changes production model state automatically.",
        ]
        if samples < MIN_REVALIDATION_SAMPLES:
            warnings.append(
                f"Need {MIN_REVALIDATION_SAMPLES} post-activation labels for a retirement recommendation; currently {samples}."
            )
        if skipped_wrong_version:
            warnings.append(f"Skipped {skipped_wrong_version} post-activation label(s) generated by another/no calibrator version.")
        if skipped_missing_probability:
            warnings.append(f"Skipped {skipped_missing_probability} label(s) without auditable raw+calibrated probability fields.")
        if retirement:
            warnings.append(
                "Live calibrated quality is materially worse than the raw model and/or its activation holdout. Revalidation/retirement is recommended."
            )

        bucket_rows: list[SLALiveMonitorBucket] = []
        for item in calibrated_metrics["buckets"]:
            bucket_rows.append(
                SLALiveMonitorBucket(
                    lower_bound=item["lower_bound"],
                    upper_bound=item["upper_bound"],
                    samples=item["samples"],
                    calibrated_mean_prediction=item["mean_prediction"],
                    observed_completion_rate=item["observed_completion_rate"],
                )
            )

        return SLALiveMonitorResponse(
            base_model_version=base_model_version,
            active_calibrator_id=active.id,
            active_calibrator_version=active.calibrator_version,
            activated_at=active.activated_at,
            post_activation_labels=samples,
            minimum_revalidation_samples=MIN_REVALIDATION_SAMPLES,
            raw_brier=raw_metrics["brier_score"],
            calibrated_brier=calibrated_metrics["brier_score"],
            raw_ece=raw_metrics["expected_calibration_error"],
            calibrated_ece=calibrated_metrics["expected_calibration_error"],
            raw_bias=raw_metrics["calibration_bias"],
            calibrated_bias=calibrated_metrics["calibration_bias"],
            holdout_calibrated_brier=float(active.calibrated_brier_test),
            holdout_calibrated_ece=float(active.calibrated_ece_test),
            status=status,
            retirement_recommended=retirement,
            warnings=warnings,
            buckets=bucket_rows,
        )
