from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.connections.orchestration import ConnectionAwareOrchestrationService
from app.features.orchestration.execution_events import CampaignExecutionEventService
from app.features.orchestration.models import ActionJob
from app.features.orchestration.preflight import CampaignExecutionPreflightService
from app.features.orchestration.preflight_learning import CampaignPreflightLearningService
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


async def _campaign_job_ids(
    *,
    session: AsyncSession,
    owner_id: UUID,
    campaign_id: UUID,
) -> set[UUID]:
    result = await session.execute(
        select(ActionJob.id).where(
            ActionJob.owner_id == owner_id,
            ActionJob.campaign_id == campaign_id,
        )
    )
    return set(result.scalars().all())


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
    """Re-run preflight immediately before planning and start with that exact safe account set."""
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

        before_job_ids = await _campaign_job_ids(
            session=session,
            owner_id=user.id,
            campaign_id=campaign_id,
        )
        launched_at = datetime.now(timezone.utc)
        raw_plan = await ConnectionAwareOrchestrationService(session).start_campaign(
            owner_id=user.id,
            campaign_id=campaign_id,
            limit=payload.action_budget,
            min_activity_score=payload.min_activity_score,
            min_readiness_score=payload.min_readiness_score,
            account_ids=preflight.recommended_account_ids,
        )
        plan = CampaignPlanResponse(**raw_plan)
        after_job_ids = await _campaign_job_ids(
            session=session,
            owner_id=user.id,
            campaign_id=campaign_id,
        )
        tracked_job_ids = sorted(after_job_ids - before_job_ids, key=str)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    post_launch_warnings: list[str] = []

    # The campaign is already active and ActionJobs may already exist at this point.
    # Never convert a successful side effect into a retry-inducing 500 because an
    # observability write failed afterwards.
    try:
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
                "new_action_jobs": len(tracked_job_ids),
            },
        )
    except Exception:
        await session.rollback()
        logger.exception(
            "Campaign started but operator_start execution event persistence failed",
            campaign_id=str(campaign_id),
            owner_id=str(user.id),
        )
        post_launch_warnings.append("Campaign started, but execution audit event persistence failed.")

    learning_snapshot_id: UUID | None = None
    try:
        snapshot = await CampaignPreflightLearningService(session).record_launch(
            owner_id=user.id,
            preflight=preflight,
            plan=plan,
            tracked_job_ids=tracked_job_ids,
            launched_at=launched_at,
        )
        learning_snapshot_id = snapshot.id
    except Exception:
        await session.rollback()
        logger.exception(
            "Campaign started but preflight decision learning snapshot persistence failed",
            campaign_id=str(campaign_id),
            owner_id=str(user.id),
        )
        post_launch_warnings.append("Campaign started, but launch decision learning snapshot persistence failed.")

    return CampaignPreflightLaunchResponse(
        preflight=preflight,
        plan=plan,
        learning_snapshot_id=learning_snapshot_id,
        learning_snapshot_warning=(" ".join(post_launch_warnings) if post_launch_warnings else None),
    )
