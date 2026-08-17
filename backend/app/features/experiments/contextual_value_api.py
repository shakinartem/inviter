from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.experiments.contextual_value import ContextualIncrementalBusinessValueService
from app.features.experiments.contextual_value_schemas import ContextualIncrementalBusinessValueResponse


router = APIRouter(prefix="/experiments", tags=["experiments", "contextual-value"])


@router.get("/contextual-value", response_model=ContextualIncrementalBusinessValueResponse)
async def contextual_business_value(
    event_type: str,
    value_unit: str,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    horizon_hours: int = Query(default=168, ge=1, le=2160),
    aggregation: str = Query(default="sum", pattern="^(sum|max)$"),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
) -> ContextualIncrementalBusinessValueResponse:
    try:
        result = await ContextualIncrementalBusinessValueService(session).analyze(
            owner_id=user.id,
            event_type=event_type,
            value_unit=value_unit,
            horizon_hours=horizon_hours,
            aggregation=aggregation,
            min_confidence=min_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ContextualIncrementalBusinessValueResponse(**result)
