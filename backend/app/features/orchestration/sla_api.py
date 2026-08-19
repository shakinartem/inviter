from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.orchestration.sla import ExecutionSLAForecastService
from app.features.orchestration.sla_calibration import ExecutionSLACalibrationService
from app.features.orchestration.sla_calibration_schemas import (
    SLACalibrationResponse,
    SLAContinuityCalibrationResponse,
    SLAFinalizationResponse,
    SLALabelAuditItem,
)
from app.features.orchestration.sla_probability import apply_active_completion_calibration
from app.features.orchestration.sla_schemas import (
    ExecutionSLAForecastHistoryItem,
    ExecutionSLAForecastRequest,
    ExecutionSLAForecastResponse,
)


router = APIRouter(prefix="/execution-sla", tags=["execution-sla", "adaptive-execution"])


@router.post("/forecast", response_model=ExecutionSLAForecastResponse)
async def forecast_execution_sla(
    payload: ExecutionSLAForecastRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionSLAForecastResponse:
    try:
        forecast = await ExecutionSLAForecastService(session).forecast(
            owner_id=user.id,
            campaign_id=payload.campaign_id,
            remaining_actions=payload.remaining_actions,
            deadline_days=payload.deadline_days,
            target_sla=payload.target_sla,
            lookback_days=payload.lookback_days,
            reserve_percentages=payload.reserve_percentages,
            simulations=payload.simulations,
            persist_snapshot=payload.persist_snapshot,
        )
        return await apply_active_completion_calibration(
            session,
            owner_id=user.id,
            forecast=forecast,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/finalize", response_model=SLAFinalizationResponse)
async def finalize_mature_execution_sla_labels(
    limit: int = Query(default=100, ge=1, le=1000),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SLAFinalizationResponse:
    return await ExecutionSLACalibrationService(session).finalize_mature_forecasts(
        owner_id=user.id,
        limit=limit,
    )


@router.get("/calibration", response_model=SLACalibrationResponse)
async def execution_sla_calibration(
    campaign_id: UUID | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=10000),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SLACalibrationResponse:
    return await ExecutionSLACalibrationService(session).calibration(
        owner_id=user.id,
        campaign_id=campaign_id,
        limit=limit,
    )


@router.get("/continuity-calibration", response_model=SLAContinuityCalibrationResponse)
async def execution_sla_continuity_calibration(
    campaign_id: UUID | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=10000),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SLAContinuityCalibrationResponse:
    return await ExecutionSLACalibrationService(session).continuity_calibration(
        owner_id=user.id,
        campaign_id=campaign_id,
        limit=limit,
    )


@router.get("/labels", response_model=list[SLALabelAuditItem])
async def execution_sla_label_audit(
    campaign_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[SLALabelAuditItem]:
    return await ExecutionSLACalibrationService(session).label_audit(
        owner_id=user.id,
        campaign_id=campaign_id,
        limit=limit,
    )


@router.get("/history", response_model=list[ExecutionSLAForecastHistoryItem])
async def forecast_history(
    campaign_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ExecutionSLAForecastHistoryItem]:
    return await ExecutionSLAForecastService(session).history(
        owner_id=user.id,
        campaign_id=campaign_id,
        limit=limit,
    )
