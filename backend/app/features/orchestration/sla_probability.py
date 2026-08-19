from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.orchestration.sla_calibrator_math import apply_mapping
from app.features.orchestration.sla_governance_models import ExecutionSLACalibrator
from app.features.orchestration.sla_models import ExecutionSLAForecastSnapshot
from app.features.orchestration.sla_schemas import ExecutionSLAForecastResponse


async def apply_active_completion_calibration(
    session: AsyncSession,
    *,
    owner_id: UUID,
    forecast: ExecutionSLAForecastResponse,
) -> ExecutionSLAForecastResponse:
    """Apply the active calibrator to point completion probability only.

    Raw Monte Carlo completion and all conservative continuity/capacity values are
    intentionally preserved. The applied model version is persisted into the
    immutable forecast-time payload for later live revalidation.
    """
    active = (
        await session.execute(
            select(ExecutionSLACalibrator)
            .where(
                ExecutionSLACalibrator.owner_id == owner_id,
                ExecutionSLACalibrator.base_model_version == forecast.model_version,
                ExecutionSLACalibrator.status == "active",
            )
            .order_by(ExecutionSLACalibrator.activated_at.desc().nullslast())
            .limit(1)
        )
    ).scalar_one_or_none()

    mapping = active.mapping if active is not None else []
    forecast.active_calibrator_version = active.calibrator_version if active is not None else None
    for scenario in forecast.scenarios:
        raw = min(max(float(scenario.modelled_workload_completion_probability), 0.0), 1.0)
        scenario.calibrated_workload_completion_probability = (
            apply_mapping(raw, mapping) if active is not None else raw
        )

    # Keep current/recommended references aligned with the calibrated scenario list.
    current = min(
        forecast.scenarios,
        key=lambda item: abs(float(item.reserve_percentage) - float(forecast.current_reserve_percentage)),
    )
    forecast.current_scenario = current
    if forecast.recommended_scenario is not None:
        reserve = float(forecast.recommended_scenario.reserve_percentage)
        forecast.recommended_scenario = min(
            forecast.scenarios,
            key=lambda item: abs(float(item.reserve_percentage) - reserve),
        )

    if active is not None:
        forecast.warnings.append(
            f"Point workload-completion probability calibrated by {active.calibrator_version}; safety and reserve decisions still use conservative raw execution policy."
        )

    if forecast.forecast_id is not None:
        snapshot = (
            await session.execute(
                select(ExecutionSLAForecastSnapshot).where(
                    ExecutionSLAForecastSnapshot.id == forecast.forecast_id,
                    ExecutionSLAForecastSnapshot.owner_id == owner_id,
                )
            )
        ).scalar_one_or_none()
        if snapshot is not None:
            payload = dict(snapshot.input_snapshot or {})
            payload["active_calibrator_version"] = forecast.active_calibrator_version
            payload["point_completion_probability_semantics"] = (
                "governed_calibrated" if active is not None else "raw_execution_sla_v1"
            )
            snapshot.input_snapshot = payload
            snapshot.scenarios_snapshot = [item.model_dump(mode="json") for item in forecast.scenarios]
            await session.commit()

    return forecast
