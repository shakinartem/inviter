from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.experiments.value import IncrementalBusinessValueService
from app.features.experiments.value_schemas import IncrementalBusinessValueResponse


router = APIRouter(prefix="/experiments", tags=["experiments", "incremental-value"])


@router.get("/value-lift", response_model=IncrementalBusinessValueResponse)
async def incremental_business_value(
    event_type: str,
    value_unit: str,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    horizon_hours: int = Query(default=168, ge=1, le=2160),
    aggregation: str = Query(default="sum", pattern="^(sum|max)$"),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
) -> IncrementalBusinessValueResponse:
    try:
        result = await IncrementalBusinessValueService(session).analyze(
            owner_id=user.id,
            event_type=event_type,
            value_unit=value_unit,
            horizon_hours=horizon_hours,
            aggregation=aggregation,
            min_confidence=min_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return IncrementalBusinessValueResponse(**result)
