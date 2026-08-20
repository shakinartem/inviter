from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.orchestration.adaptive import POLICY_VERSION, AdaptiveExecutionService
from app.features.orchestration.adaptive_schemas import (
    AdaptiveAssignmentEventResponse,
    AdaptiveExecutionRequest,
    AdaptivePlanResponse,
    AdaptivePolicyResponse,
)


router = APIRouter(prefix="/adaptive-execution", tags=["adaptive-execution", "orchestration"])


@router.get("/policy", response_model=AdaptivePolicyResponse)
async def adaptive_policy() -> AdaptivePolicyResponse:
    return AdaptivePolicyResponse(policy_version=POLICY_VERSION)


@router.post("/preview", response_model=AdaptivePlanResponse)
async def preview_rebalance(
    payload: AdaptiveExecutionRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> AdaptivePlanResponse:
    try:
        plan = await AdaptiveExecutionService(session).preview(
            owner_id=user.id,
            source_account_id=payload.source_account_id,
            campaign_id=payload.campaign_id,
            reason=payload.reason,
            max_jobs=payload.max_jobs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AdaptivePlanResponse(**plan.public_dict())


@router.post("/rebalance", response_model=AdaptivePlanResponse)
async def rebalance(
    payload: AdaptiveExecutionRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> AdaptivePlanResponse:
    try:
        plan = await AdaptiveExecutionService(session).rebalance_account(
            owner_id=user.id,
            source_account_id=payload.source_account_id,
            campaign_id=payload.campaign_id,
            reason=payload.reason,
            max_jobs=payload.max_jobs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AdaptivePlanResponse(**plan.public_dict())


@router.get("/events", response_model=list[AdaptiveAssignmentEventResponse])
async def assignment_events(
    campaign_id: UUID | None = Query(default=None),
    account_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[AdaptiveAssignmentEventResponse]:
    events = await AdaptiveExecutionService(session).events(
        owner_id=user.id,
        campaign_id=campaign_id,
        account_id=account_id,
        limit=limit,
    )
    return [
        AdaptiveAssignmentEventResponse(
            id=item.id,
            campaign_id=item.campaign_id,
            action_job_id=item.action_job_id,
            from_account_id=item.from_account_id,
            to_account_id=item.to_account_id,
            reason=item.reason,
            policy_version=item.policy_version,
            previous_scheduled_at=item.previous_scheduled_at,
            new_scheduled_at=item.new_scheduled_at,
            details=item.details,
            created_at=item.created_at,
        )
        for item in events
    ]
