from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.experiments.meta import IncrementalYieldMetaService
from app.features.experiments.models import CampaignExperiment
from app.features.experiments.value import IncrementalBusinessValueService
from app.features.experiments.evidence_health_schemas import EvidenceHealthRequest


MIN_WINDOW_EXPERIMENTS = 2
HETEROGENEITY_WATCH = 50.0
WATCH_Z = 1.28


class CausalEvidenceHealthService:
    """Detect stale or shifting randomized treatment effects over time."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def analyze(
        self,
        *,
        owner_id: UUID,
        payload: EvidenceHealthRequest,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        event_type = payload.event_type.strip().lower().replace(" ", "_")
        if payload.objective == "incremental_business_value":
            assert payload.value_unit is not None
            global_result = await IncrementalBusinessValueService(self.session).analyze(
                owner_id=owner_id,
                event_type=event_type,
                value_unit=payload.value_unit,
                horizon_hours=payload.horizon_hours,
                aggregation=payload.value_aggregation or "sum",
                min_confidence=min_confidence,
            )
            effect_rows = [
                {
                    "experiment_id": row["experiment_id"],
                    "effect": float(row["incremental_value_per_unit"]),
                    "se": max(float(row["standard_error"]), 1e-9),
                }
                for row in global_result["rows"]
            ]
        else:
            global_result = await IncrementalYieldMetaService(self.session).analyze(
                owner_id=owner_id,
                stage=payload.stage,
                event_type=event_type,
                horizon_hours=payload.horizon_hours,
                min_confidence=min_confidence,
            )
            effect_rows = [
                {
                    "experiment_id": row["experiment_id"],
                    "effect": float(row["lift_percentage_points"]),
                    "se": max(float(row["standard_error_percentage_points"]), 1e-9),
                }
                for row in global_result["rows"]
            ]

        warnings = list(dict.fromkeys(global_result.get("warnings", [])))
        if not effect_rows:
            warnings.append("no_mature_randomized_effect_rows")
            return self._empty(payload, event_type, warnings)

        ids = [row["experiment_id"] for row in effect_rows]
        timestamps_result = await self.session.execute(
            select(CampaignExperiment.id, CampaignExperiment.assigned_at).where(
                CampaignExperiment.owner_id == owner_id,
                CampaignExperiment.id.in_(ids),
                CampaignExperiment.assigned_at.is_not(None),
            )
        )
        assigned_at = {
            experiment_id: self._aware(ts)
            for experiment_id, ts in timestamps_result.all()
            if ts is not None
        }
        rows = [row for row in effect_rows if row["experiment_id"] in assigned_at]
        if not rows:
            warnings.append("experiment_timestamps_unavailable")
            return self._empty(payload, event_type, warnings)

        now = datetime.now(timezone.utc)
        horizon = timedelta(hours=payload.horizon_hours)
        latest_assignment = max(assigned_at[row["experiment_id"]] for row in rows)
        latest_mature_completion = latest_assignment + horizon
        age_days = max((now - latest_mature_completion).total_seconds() / 86400.0, 0.0)

        mature_cutoff = now - horizon
        recent_start = mature_cutoff - timedelta(days=payload.recent_window_days)
        recent_rows = [
            row for row in rows
            if recent_start <= assigned_at[row["experiment_id"]] <= mature_cutoff
        ]
        historical_rows = [
            row for row in rows
            if assigned_at[row["experiment_id"]] < recent_start
        ]

        recent = self._pool(recent_rows)
        historical = self._pool(historical_rows)
        drift_difference = None
        drift_low = None
        drift_high = None
        drift_z = None
        status = "insufficient"
        recommend_reexperiment = True

        if age_days > payload.max_evidence_age_days:
            status = "stale"
            warnings.append("latest_mature_randomized_evidence_is_stale")
        elif recent["experiments"] < MIN_WINDOW_EXPERIMENTS:
            warnings.append("too_few_recent_mature_experiments")
        elif historical["experiments"] < MIN_WINDOW_EXPERIMENTS:
            warnings.append("too_few_historical_experiments_for_drift_baseline")
        else:
            assert recent["estimate"] is not None and historical["estimate"] is not None
            assert recent["variance"] is not None and historical["variance"] is not None
            drift_difference = recent["estimate"] - historical["estimate"]
            drift_se = math.sqrt(recent["variance"] + historical["variance"])
            drift_z = drift_difference / drift_se if drift_se > 0 else 0.0
            drift_low = drift_difference - 1.96 * drift_se
            drift_high = drift_difference + 1.96 * drift_se
            if drift_low > 0:
                status = "drift_positive"
                warnings.append("recent_randomized_effect_is_materially_higher")
            elif drift_high < 0:
                status = "drift_negative"
                warnings.append("recent_randomized_effect_is_materially_lower")
            elif (
                abs(drift_z) >= WATCH_Z
                or (recent["i_squared_percent"] or 0.0) >= HETEROGENEITY_WATCH
                or (historical["i_squared_percent"] or 0.0) >= HETEROGENEITY_WATCH
            ):
                status = "watch"
                warnings.append("effect_shift_or_heterogeneity_needs_more_recent_randomization")
            else:
                status = "stable"
                recommend_reexperiment = False

        return {
            "objective": payload.objective,
            "event_type": event_type,
            "value_unit": payload.value_unit,
            "horizon_hours": payload.horizon_hours,
            "recent_window_days": payload.recent_window_days,
            "max_evidence_age_days": payload.max_evidence_age_days,
            "latest_mature_assignment_at": latest_assignment,
            "evidence_age_days": round(age_days, 2),
            "recent": self._public_window(recent),
            "historical": self._public_window(historical),
            "drift_difference": round(drift_difference, 4) if drift_difference is not None else None,
            "drift_confidence_low": round(drift_low, 4) if drift_low is not None else None,
            "drift_confidence_high": round(drift_high, 4) if drift_high is not None else None,
            "drift_z_score": round(drift_z, 3) if drift_z is not None else None,
            "status": status,
            "recommend_reexperiment": recommend_reexperiment,
            "warnings": list(dict.fromkeys(warnings)),
        }

    @staticmethod
    def _pool(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "experiments": 0,
                "estimate": None,
                "confidence_low": None,
                "confidence_high": None,
                "i_squared_percent": None,
                "variance": None,
            }
        variances = [max(float(row["se"]) ** 2, 1e-12) for row in rows]
        fixed_weights = [1.0 / variance for variance in variances]
        fixed_mean = sum(weight * float(row["effect"]) for weight, row in zip(fixed_weights, rows)) / sum(fixed_weights)
        q = sum(weight * (float(row["effect"]) - fixed_mean) ** 2 for weight, row in zip(fixed_weights, rows))
        df = len(rows) - 1
        sum_w = sum(fixed_weights)
        c = sum_w - sum(weight * weight for weight in fixed_weights) / sum_w
        tau2 = max(0.0, (q - df) / c) if c > 0 and df > 0 else 0.0
        random_weights = [1.0 / (variance + tau2) for variance in variances]
        estimate = sum(weight * float(row["effect"]) for weight, row in zip(random_weights, rows)) / sum(random_weights)
        variance = 1.0 / sum(random_weights)
        se = math.sqrt(variance)
        i2 = max(0.0, (q - df) / q * 100.0) if q > 0 and df > 0 else 0.0
        return {
            "experiments": len(rows),
            "estimate": estimate,
            "confidence_low": estimate - 1.96 * se,
            "confidence_high": estimate + 1.96 * se,
            "i_squared_percent": i2,
            "variance": variance,
        }

    @staticmethod
    def _public_window(window: dict[str, Any]) -> dict[str, Any]:
        return {
            "experiments": window["experiments"],
            "estimate": round(window["estimate"], 4) if window["estimate"] is not None else None,
            "confidence_low": round(window["confidence_low"], 4) if window["confidence_low"] is not None else None,
            "confidence_high": round(window["confidence_high"], 4) if window["confidence_high"] is not None else None,
            "i_squared_percent": round(window["i_squared_percent"], 2) if window["i_squared_percent"] is not None else None,
        }

    @staticmethod
    def _empty(payload: EvidenceHealthRequest, event_type: str, warnings: list[str]) -> dict[str, Any]:
        empty_window = {
            "experiments": 0,
            "estimate": None,
            "confidence_low": None,
            "confidence_high": None,
            "i_squared_percent": None,
        }
        return {
            "objective": payload.objective,
            "event_type": event_type,
            "value_unit": payload.value_unit,
            "horizon_hours": payload.horizon_hours,
            "recent_window_days": payload.recent_window_days,
            "max_evidence_age_days": payload.max_evidence_age_days,
            "latest_mature_assignment_at": None,
            "evidence_age_days": None,
            "recent": empty_window,
            "historical": empty_window,
            "drift_difference": None,
            "drift_confidence_low": None,
            "drift_confidence_high": None,
            "drift_z_score": None,
            "status": "insufficient",
            "recommend_reexperiment": True,
            "warnings": list(dict.fromkeys(warnings)),
        }

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
