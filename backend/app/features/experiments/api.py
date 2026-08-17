from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.experiments.schemas import (
    CampaignExperimentResponse,
    ExperimentAssignmentListResponse,
    ExperimentAssignmentResponse,
)
from app.features.experiments.service import CampaignExperimentService


router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=list[CampaignExperimentResponse])
async def list_experiments(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CampaignExperimentResponse]:
    items = await CampaignExperimentService(session).list_for_owner(user.id)
    return [CampaignExperimentResponse.model_validate(item) for item in items]


@router.get("/campaigns/{campaign_id}", response_model=CampaignExperimentResponse)
async def get_campaign_experiment(
    campaign_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CampaignExperimentResponse:
    item = await CampaignExperimentService(session).get_for_campaign(
        owner_id=user.id,
        campaign_id=campaign_id,
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign experiment not found")
    return CampaignExperimentResponse.model_validate(item)


@router.get(
    "/campaigns/{campaign_id}/assignments",
    response_model=ExperimentAssignmentListResponse,
)
async def list_campaign_assignments(
    campaign_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    variant: str | None = Query(default=None, pattern="^(treatment|holdout)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> ExperimentAssignmentListResponse:
    try:
        items, total = await CampaignExperimentService(session).assignments(
            owner_id=user.id,
            campaign_id=campaign_id,
            variant=variant,
            skip=skip,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ExperimentAssignmentListResponse(
        items=[ExperimentAssignmentResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )
