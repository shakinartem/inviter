from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.orchestration.schemas import (
    ActionJobListResponse,
    ActionJobResponse,
    CampaignActionStatsResponse,
    CampaignPlanRequest,
    CampaignPlanResponse,
)
from app.features.orchestration.service import OrchestrationService


router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@router.post("/campaigns/{campaign_id}/plan", response_model=CampaignPlanResponse)
async def plan_campaign(
    campaign_id: UUID,
    payload: CampaignPlanRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CampaignPlanResponse:
    service = OrchestrationService(session)
    try:
        result = await service.plan_campaign(
            owner_id=user.id,
            campaign_id=campaign_id,
            limit=payload.limit,
            min_activity_score=payload.min_activity_score,
            min_readiness_score=payload.min_readiness_score,
            account_ids=payload.account_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CampaignPlanResponse(**result)


@router.post("/campaigns/{campaign_id}/start", response_model=CampaignPlanResponse)
async def start_campaign(
    campaign_id: UUID,
    payload: CampaignPlanRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CampaignPlanResponse:
    service = OrchestrationService(session)
    try:
        result = await service.start_campaign(
            owner_id=user.id,
            campaign_id=campaign_id,
            limit=payload.limit,
            min_activity_score=payload.min_activity_score,
            min_readiness_score=payload.min_readiness_score,
            account_ids=payload.account_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CampaignPlanResponse(**result)


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = OrchestrationService(session)
    if not await service.pause_campaign(owner_id=user.id, campaign_id=campaign_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return {"success": True, "status": "paused"}


@router.post("/campaigns/{campaign_id}/stop")
async def stop_campaign(
    campaign_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = OrchestrationService(session)
    if not await service.stop_campaign(owner_id=user.id, campaign_id=campaign_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return {"success": True, "status": "completed"}


@router.get("/jobs", response_model=ActionJobListResponse)
async def list_jobs(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    campaign_id: UUID | None = Query(default=None),
    job_status: str | None = Query(default=None, alias="status", max_length=32),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> ActionJobListResponse:
    service = OrchestrationService(session)
    items, total = await service.list_jobs(
        owner_id=user.id,
        campaign_id=campaign_id,
        status=job_status,
        skip=skip,
        limit=limit,
    )
    return ActionJobListResponse(
        items=[ActionJobResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/campaigns/{campaign_id}/stats",
    response_model=CampaignActionStatsResponse,
)
async def campaign_stats(
    campaign_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CampaignActionStatsResponse:
    service = OrchestrationService(session)
    try:
        result = await service.campaign_stats(owner_id=user.id, campaign_id=campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CampaignActionStatsResponse(**result)
