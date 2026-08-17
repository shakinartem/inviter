from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.experiments.meta import IncrementalYieldMetaService
from app.features.experiments.meta_schemas import IncrementalYieldMetaResponse


router = APIRouter(prefix="/experiments", tags=["experiments", "incremental-yield"])


@router.get("/meta-lift", response_model=IncrementalYieldMetaResponse)
async def meta_lift(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    stage: str = Query(default="business", pattern="^(engagement|business)$"),
    event_type: str = Query(default="converted", min_length=1, max_length=64),
    horizon_hours: int = Query(default=168, ge=1, le=2160),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
) -> IncrementalYieldMetaResponse:
    try:
        result = await IncrementalYieldMetaService(session).analyze(
            owner_id=user.id,
            stage=stage,
            event_type=event_type,
            horizon_hours=horizon_hours,
            min_confidence=min_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return IncrementalYieldMetaResponse(**result)
