from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.orchestration.resilience import CampaignResilienceService
from app.features.orchestration.resilience_schemas import CampaignResilienceResponse


router = APIRouter(prefix="/adaptive-execution/resilience", tags=["adaptive-execution", "resilience"])


@router.get("/{campaign_id}", response_model=CampaignResilienceResponse)
async def campaign_resilience(
    campaign_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CampaignResilienceResponse:
    try:
        return await CampaignResilienceService(session).evaluate(
            owner_id=user.id,
            campaign_id=campaign_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
