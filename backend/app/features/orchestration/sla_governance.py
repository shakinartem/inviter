from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.orchestration.sla import MODEL_VERSION
from app.features.orchestration.sla_calibration import calibration_metrics, current_workload_completion_probability
from app.features.orchestration.sla_governance_models import ExecutionSLACalibrator
from app.features.orchestration.sla_governance_schemas import (
    SLACalibratorApplyResponse,
    SLACalibratorBin,
    SLACalibratorResponse,
    SLACalibratorTrainResponse,
)
from app.features.orchestration.sla_models import ExecutionSLAForecastSnapshot


BIN_COUNT = 10


def build_monotonic_mapping(
    predictions: list[float],
    outcomes: list[int],
    *,
    prior_strength: float = 8.0,
) -> list[dict]:
    """Build fixed-bin, identity-shrunk monotonic probability mapping.

    Each bin is shrunk toward its mean raw prediction before pooled-adjacent-
    violators enforces monotonicity. This keeps sparse bins near identity instead
    of letting a few labels create extreme probabilities.
    """
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    prior = max(float(prior_strength), 1.0)
    bins: list[dict] = []
    width = 1.0 / BIN_COUNT
    for index in range(BIN_COUNT):
        lower = index * width
        upper = 1.0 if index == BIN_COUNT - 1 else (index + 1) * width
        selected = [
            (min(max(float(p), 0.0), 1.0), 1 if int(y) else 0)
            for p, y in zip(predictions, outcomes)
            if lower <= min(max(float(p), 0.0), 1.0) <= upper
            and (index == BIN_COUNT - 1 or min(max(float(p), 0.0), 1.0) < upper)
        ]
        midpoint = (lower + upper) / 2.0
        mean_raw = sum(p for p, _ in selected) / len(selected) if selected else midpoint
        successes = sum(y for _, y in selected)
        observed = successes / len(selected) if selected else None
        posterior = (successes + prior * mean_raw) / (len(selected) + prior)
        bins.append(
            {
                "lower_bound": round(lower, 4),
                "upper_bound": round(upper, 4),
                "samples": len(selected),
                "mean_raw_prediction": round(mean_raw, 6),
                "observed_rate": round(observed, 6) if observed is not None else None,
                "calibrated_probability": float(posterior),
                "_weight": len(selected) + prior,
            }
        )

    # Weighted PAVA over adjacent bins.
    blocks: list[dict] = []
    for index, item in enumerate(bins):
        block = {
            "start": index,
            "end": index,
            "weight": float(item["_weight"]),
            "value": float(item["calibrated_probability"]),
        }
        blocks.append(block)
        while len(blocks) >= 2 and blocks[-2]["value"] > blocks[-1]["value"]:
            right = blocks.pop()
            left = blocks.pop()
            weight = left["weight"] + right["weight"]
            value = (left["value"] * left["weight"] + right["value"] * right["weight"]) / weight
            blocks.append(
                {
                    "start": left["start"],
                    "end": right["end"],
                    "weight": weight,
                    "value": value,
                }
            )

    for block in blocks:
        for index in range(block["start"], block["end"] + 1):
            bins[index]["calibrated_probability"] = round(min(max(block["value"], 0.0), 1.0), 6)
            bins[index].pop("_weight", None)
    return bins


def apply_mapping(probability: float, mapping: list[dict]) -> float:
    p = min(max(float(probability), 0.0), 1.0)
    if not mapping:
        return p
    for index, item in enumerate(mapping):
        lower = float(item["lower_bound"])
        upper = float(item["upper_bound"])
        if lower <= p < upper or (index == len(mapping) - 1 and p <= upper):
            return min(max(float(item["calibrated_probability"]), 0.0), 1.0)
    return p


def activation_eligible(
    *,
    test_count: int,
    raw_brier: float,
    calibrated_brier: float,
    raw_ece: float,
    calibrated_ece: float,
    raw_bias: float,
    calibrated_bias: float,
) -> bool:
    return (
        int(test_count) >= 20
        and calibrated_brier <= raw_brier + 0.002
        and calibrated_ece <= raw_ece + 0.02
        and abs(calibrated_bias) <= abs(raw_bias) + 0.02
    )


class ExecutionSLAGovernanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def train_candidate(
        self,
        *,
        owner_id: UUID,
        base_model_version: str = MODEL_VERSION,
        min_samples: int = 100,
        test_fraction: float = 0.20,
        prior_strength: float = 8.0,
    ) -> SLACalibratorTrainResponse:
        rows = await self._eligible_rows(owner_id=owner_id, base_model_version=base_model_version)
        samples: list[tuple[ExecutionSLAForecastSnapshot, float, int]] = []
        for row in rows:
            prediction = current_workload_completion_probability(row)
            if prediction is None or row.actual_met_sla is None:
                continue
            samples.append((row, prediction, 1 if row.actual_met_sla else 0))

        required = max(int(min_samples), 100)
        if len(samples) < required:
            return SLACalibratorTrainResponse(
                status="insufficient",
                eligible_samples=len(samples),
                minimum_required=required,
                calibrator=None,
                warnings=[
                    "At least 100 intervention-clean mature forecasts are required before fitting a calibration layer.",
                    "Raw execution-sla-v1 remains active; no probability correction was created.",
                ],
            )

        test_count = max(20, int(round(len(samples) * float(test_fraction))))
        test_count = min(test_count, len(samples) - 50)
        train = samples[:-test_count]
        test = samples[-test_count:]
        if len(train) < 50 or len(test) < 20:
            return SLACalibratorTrainResponse(
                status="insufficient_split",
                eligible_samples=len(samples),
                minimum_required=required,
                calibrator=None,
                warnings=["Not enough chronological train/test data after the requested split."],
            )

        train_predictions = [item[1] for item in train]
        train_outcomes = [item[2] for item in train]
        mapping = build_monotonic_mapping(
            train_predictions,
            train_outcomes,
            prior_strength=prior_strength,
        )

        raw_test = [item[1] for item in test]
        test_outcomes = [item[2] for item in test]
        calibrated_test = [apply_mapping(value, mapping) for value in raw_test]
        raw_metrics = calibration_metrics(raw_test, test_outcomes)
        calibrated_metrics = calibration_metrics(calibrated_test, test_outcomes)

        eligible = activation_eligible(
            test_count=len(test),
            raw_brier=float(raw_metrics["brier_score"] or 0.0),
            calibrated_brier=float(calibrated_metrics["brier_score"] or 0.0),
            raw_ece=float(raw_metrics["expected_calibration_error"] or 0.0),
            calibrated_ece=float(calibrated_metrics["expected_calibration_error"] or 0.0),
            raw_bias=float(raw_metrics["calibration_bias"] or 0.0),
            calibrated_bias=float(calibrated_metrics["calibration_bias"] or 0.0),
        )

        now = datetime.now(timezone.utc)
        cutoff = self._aware(train[-1][0].created_at)
        version = f"{base_model_version}-cal-{now.strftime('%Y%m%d%H%M%S')}"
        model = ExecutionSLACalibrator(
            owner_id=owner_id,
            base_model_version=base_model_version,
            calibrator_version=version,
            status="candidate",
            sample_count=len(samples),
            train_count=len(train),
            test_count=len(test),
            training_cutoff_at=cutoff,
            raw_brier_test=float(raw_metrics["brier_score"] or 0.0),
            calibrated_brier_test=float(calibrated_metrics["brier_score"] or 0.0),
            raw_ece_test=float(raw_metrics["expected_calibration_error"] or 0.0),
            calibrated_ece_test=float(calibrated_metrics["expected_calibration_error"] or 0.0),
            raw_bias_test=float(raw_metrics["calibration_bias"] or 0.0),
            calibrated_bias_test=float(calibrated_metrics["calibration_bias"] or 0.0),
            mapping=mapping,
            training_metadata={
                "activation_eligible": eligible,
                "prior_strength": float(prior_strength),
                "test_fraction": float(test_fraction),
                "split": "chronological_oldest_train_newest_test",
                "label_status": "labeled_only",
                "excluded": ["intervened", "ineligible_queue", "pending"],
            },
            trained_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        warnings = [] if eligible else [
            "Candidate did not improve or preserve chronological holdout quality within governance tolerances.",
            "Activation is blocked; raw execution-sla-v1 remains the production point forecast.",
        ]
        return SLACalibratorTrainResponse(
            status="candidate_ready" if eligible else "candidate_rejected_by_holdout",
            eligible_samples=len(samples),
            minimum_required=required,
            calibrator=self._response(model),
            warnings=warnings,
        )

    async def activate(
        self,
        *,
        owner_id: UUID,
        calibrator_id: UUID,
    ) -> SLACalibratorResponse:
        model = await self._get(owner_id=owner_id, calibrator_id=calibrator_id)
        if model is None:
            raise ValueError("Calibrator not found")
        if not bool((model.training_metadata or {}).get("activation_eligible")):
            raise ValueError("Calibrator is not eligible for activation")
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(ExecutionSLACalibrator)
            .where(
                ExecutionSLACalibrator.owner_id == owner_id,
                ExecutionSLACalibrator.base_model_version == model.base_model_version,
                ExecutionSLACalibrator.status == "active",
                ExecutionSLACalibrator.id != model.id,
            )
            .values(status="retired", retired_at=now)
        )
        model.status = "active"
        model.activated_at = now
        model.retired_at = None
        await self.session.commit()
        await self.session.refresh(model)
        return self._response(model)

    async def retire(
        self,
        *,
        owner_id: UUID,
        calibrator_id: UUID,
    ) -> SLACalibratorResponse:
        model = await self._get(owner_id=owner_id, calibrator_id=calibrator_id)
        if model is None:
            raise ValueError("Calibrator not found")
        model.status = "retired"
        model.retired_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(model)
        return self._response(model)

    async def list_calibrators(
        self,
        *,
        owner_id: UUID,
        base_model_version: str | None = None,
        limit: int = 100,
    ) -> list[SLACalibratorResponse]:
        stmt = select(ExecutionSLACalibrator).where(ExecutionSLACalibrator.owner_id == owner_id)
        if base_model_version:
            stmt = stmt.where(ExecutionSLACalibrator.base_model_version == base_model_version)
        result = await self.session.execute(
            stmt.order_by(ExecutionSLACalibrator.trained_at.desc()).limit(max(1, min(int(limit), 500)))
        )
        return [self._response(item) for item in result.scalars().all()]

    async def apply_active(
        self,
        *,
        owner_id: UUID,
        raw_probability: float,
        base_model_version: str = MODEL_VERSION,
    ) -> SLACalibratorApplyResponse:
        result = await self.session.execute(
            select(ExecutionSLACalibrator)
            .where(
                ExecutionSLACalibrator.owner_id == owner_id,
                ExecutionSLACalibrator.base_model_version == base_model_version,
                ExecutionSLACalibrator.status == "active",
            )
            .order_by(ExecutionSLACalibrator.activated_at.desc().nullslast())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        raw = min(max(float(raw_probability), 0.0), 1.0)
        if model is None:
            return SLACalibratorApplyResponse(
                calibrator_version=None,
                raw_probability=raw,
                calibrated_probability=raw,
            )
        return SLACalibratorApplyResponse(
            calibrator_version=model.calibrator_version,
            raw_probability=raw,
            calibrated_probability=apply_mapping(raw, model.mapping or []),
        )

    async def _eligible_rows(
        self,
        *,
        owner_id: UUID,
        base_model_version: str,
    ) -> list[ExecutionSLAForecastSnapshot]:
        result = await self.session.execute(
            select(ExecutionSLAForecastSnapshot)
            .where(
                ExecutionSLAForecastSnapshot.owner_id == owner_id,
                ExecutionSLAForecastSnapshot.model_version == base_model_version,
                ExecutionSLAForecastSnapshot.label_status == "labeled",
                ExecutionSLAForecastSnapshot.actual_met_sla.is_not(None),
            )
            .order_by(ExecutionSLAForecastSnapshot.created_at.asc())
            .limit(10000)
        )
        return list(result.scalars().all())

    async def _get(self, *, owner_id: UUID, calibrator_id: UUID) -> ExecutionSLACalibrator | None:
        return (
            await self.session.execute(
                select(ExecutionSLACalibrator).where(
                    ExecutionSLACalibrator.id == calibrator_id,
                    ExecutionSLACalibrator.owner_id == owner_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @staticmethod
    def _response(model: ExecutionSLACalibrator) -> SLACalibratorResponse:
        return SLACalibratorResponse(
            id=model.id,
            base_model_version=model.base_model_version,
            calibrator_version=model.calibrator_version,
            status=model.status,
            sample_count=model.sample_count,
            train_count=model.train_count,
            test_count=model.test_count,
            training_cutoff_at=model.training_cutoff_at,
            raw_brier_test=model.raw_brier_test,
            calibrated_brier_test=model.calibrated_brier_test,
            raw_ece_test=model.raw_ece_test,
            calibrated_ece_test=model.calibrated_ece_test,
            raw_bias_test=model.raw_bias_test,
            calibrated_bias_test=model.calibrated_bias_test,
            activation_eligible=bool((model.training_metadata or {}).get("activation_eligible")),
            mapping=[SLACalibratorBin(**item) for item in (model.mapping or [])],
            trained_at=model.trained_at,
            activated_at=model.activated_at,
            retired_at=model.retired_at,
        )
