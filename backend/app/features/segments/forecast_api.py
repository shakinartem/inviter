from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.segments.forecast import SegmentYieldForecastService
from app.features.segments.forecast_schemas import SegmentYieldForecastResponse


router = APIRouter(prefix="/segments", tags=["segments", "forecast"])


@router.get("/{segment_id}/forecast", response_model=SegmentYieldForecastResponse)
async def forecast_segment_yield(
    segment_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    stage: str = Query(default="business", pattern="^(engagement|business)$"),
    event_type: str = Query(default="converted", min_length=1, max_length=64),
    horizon_hours: int = Query(default=168, ge=1, le=2160),
    budget: int = Query(default=1000, ge=1, le=50000),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
) -> SegmentYieldForecastResponse:
    try:
        result = await SegmentYieldForecastService(session).forecast(
            owner_id=user.id,
            segment_id=segment_id,
            stage=stage,
            event_type=event_type,
            horizon_hours=horizon_hours,
            budget=budget,
            min_confidence=min_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SegmentYieldForecastResponse(**result)
