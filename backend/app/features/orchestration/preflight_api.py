from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.connections.orchestration import ConnectionAwareOrchestrationService
from app.features.orchestration.execution_events import CampaignExecutionEventService
from app.features.orchestration.preflight import CampaignExecutionPreflightService
from app.features.orchestration.preflight_schemas import (
    CampaignPreflightLaunchResponse,
    CampaignPreflightRequest,
    CampaignPreflightResponse,
)
from app.features.orchestration.schemas import CampaignPlanResponse


router = APIRouter(prefix="/orchestration/campaigns", tags=["orchestration", "preflight"])


async def _evaluate(
    *,
    campaign_id: UUID,
    payload: CampaignPreflightRequest,
    user_id: UUID,
    session: AsyncSession,
) -> CampaignPreflightResponse:
    return await CampaignExecutionPreflightService(session).evaluate(
        owner_id=user_id,
        campaign_id=campaign_id,
        action_budget=payload.action_budget,
        deadline_days=payload.deadline_days,
        min_activity_score=payload.min_activity_score,
        min_readiness_score=payload.min_readiness_score,
        account_ids=payload.account_ids,
    )


@router.post("/{campaign_id}/preflight", response_model=CampaignPreflightResponse)
async def campaign_execution_preflight(
    campaign_id: UUID,
    payload: CampaignPreflightRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CampaignPreflightResponse:
    try:
        return await _evaluate(
            campaign_id=campaign_id,
            payload=payload,
            user_id=user.id,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{campaign_id}/preflight/start", response_model=CampaignPreflightLaunchResponse)
async def start_campaign_after_fresh_preflight(
    campaign_id: UUID,
    payload: CampaignPreflightRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CampaignPreflightLaunchResponse:
    """Re-run preflight immediately before planning and start with that exact pool."""
    try:
        preflight = await _evaluate(
            campaign_id=campaign_id,
            payload=payload,
            user_id=user.id,
            session=session,
        )
        if preflight.decision == "block":
            blocking = [item.message for item in preflight.checks if item.blocking and item.status == "block"]
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Campaign launch blocked by fresh execution preflight",
                    "blocking_checks": blocking,
                },
            )

        plan = await ConnectionAwareOrchestrationService(session).start_campaign(
            owner_id=user.id,
            campaign_id=campaign_id,
            limit=payload.action_budget,
            min_activity_score=payload.min_activity_score,
            min_readiness_score=payload.min_readiness_score,
            account_ids=preflight.recommended_account_ids,
        )
        await CampaignExecutionEventService(session).record(
            owner_id=user.id,
            campaign_id=campaign_id,
            event_type="operator_start",
            actor_type="user",
            actor_user_id=user.id,
            details={
                "path": "execution_preflight",
                "preflight_decision": preflight.decision,
                "action_budget": payload.action_budget,
                "deadline_days": payload.deadline_days,
                "evaluated_account_ids": [str(item) for item in preflight.recommended_account_ids],
            },
        )
        return CampaignPreflightLaunchResponse(
            preflight=preflight,
            plan=CampaignPlanResponse(**plan),
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
