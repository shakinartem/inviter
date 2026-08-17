from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.experiments.analysis import CausalLiftService
from app.features.experiments.analysis_schemas import CampaignCausalLiftResponse


router = APIRouter(prefix="/experiments", tags=["experiments", "causal-analysis"])


@router.get(
    "/campaigns/{campaign_id}/lift",
    response_model=CampaignCausalLiftResponse,
)
async def campaign_causal_lift(
    campaign_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    stage: str = Query(default="business", pattern="^(engagement|business)$"),
    event_type: str = Query(default="converted", min_length=1, max_length=64),
    horizon_hours: int = Query(default=168, ge=1, le=2160),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
) -> CampaignCausalLiftResponse:
    try:
        result = await CausalLiftService(session).campaign_lift(
            owner_id=user.id,
            campaign_id=campaign_id,
            stage=stage,
            event_type=event_type,
            horizon_hours=horizon_hours,
            min_confidence=min_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CampaignCausalLiftResponse(**result)
