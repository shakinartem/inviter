from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.orchestration.preflight import CampaignExecutionPreflightService
from app.features.orchestration.preflight_schemas import CampaignPreflightRequest, CampaignPreflightResponse


router = APIRouter(prefix="/orchestration/campaigns", tags=["orchestration", "preflight"])


@router.post("/{campaign_id}/preflight", response_model=CampaignPreflightResponse)
async def campaign_execution_preflight(
    campaign_id: UUID,
    payload: CampaignPreflightRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CampaignPreflightResponse:
    try:
        return await CampaignExecutionPreflightService(session).evaluate(
            owner_id=user.id,
            campaign_id=campaign_id,
            action_budget=payload.action_budget,
            deadline_days=payload.deadline_days,
            min_activity_score=payload.min_activity_score,
            min_readiness_score=payload.min_readiness_score,
            account_ids=payload.account_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
