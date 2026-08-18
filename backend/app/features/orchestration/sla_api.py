from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.orchestration.sla import ExecutionSLAForecastService
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
        return await ExecutionSLAForecastService(session).forecast(
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
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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
