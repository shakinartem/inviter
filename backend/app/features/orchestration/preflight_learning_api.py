from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.orchestration.preflight_learning import (
    PREFLIGHT_POLICY_VERSION,
    CampaignPreflightLearningService,
)
from app.features.orchestration.preflight_learning_schemas import (
    PreflightDecisionFinalizationResponse,
    PreflightDecisionHistoryItem,
    PreflightDecisionPerformanceResponse,
)


router = APIRouter(prefix="/orchestration/preflights", tags=["orchestration", "preflight-learning"])


@router.post("/finalize", response_model=PreflightDecisionFinalizationResponse)
async def finalize_preflight_decisions(
    limit: int = Query(default=250, ge=1, le=1000),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> PreflightDecisionFinalizationResponse:
    return await CampaignPreflightLearningService(session).finalize_mature(
        owner_id=user.id,
        limit=limit,
    )


@router.get("/history", response_model=list[PreflightDecisionHistoryItem])
async def preflight_decision_history(
    campaign_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[PreflightDecisionHistoryItem]:
    return await CampaignPreflightLearningService(session).history(
        owner_id=user.id,
        campaign_id=campaign_id,
        limit=limit,
    )


@router.get("/performance", response_model=PreflightDecisionPerformanceResponse)
async def preflight_decision_performance(
    policy_version: str = Query(default=PREFLIGHT_POLICY_VERSION, min_length=1, max_length=64),
    limit: int = Query(default=10000, ge=1, le=10000),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> PreflightDecisionPerformanceResponse:
    return await CampaignPreflightLearningService(session).performance(
        owner_id=user.id,
        policy_version=policy_version,
        limit=limit,
    )
