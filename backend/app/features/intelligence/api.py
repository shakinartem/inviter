from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.intelligence.schemas import (
    AudienceListResponse,
    AudienceMemberResponse,
    CommunityEnrichRequest,
    CommunityEnrichResponse,
    CommunityScoreRequest,
    CommunityScoreResponse,
)
from app.features.intelligence.scoring import CommunityScoreInput, score_community
from app.features.intelligence.service import IntelligenceService


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.post("/community-score", response_model=CommunityScoreResponse)
async def preview_community_score(
    payload: CommunityScoreRequest,
    _user=Depends(get_current_active_user),
) -> CommunityScoreResponse:
    result = score_community(CommunityScoreInput(**payload.model_dump()))
    return CommunityScoreResponse(**result.as_dict())


@router.post(
    "/communities/{community_id}/enrich",
    response_model=CommunityEnrichResponse,
    status_code=status.HTTP_200_OK,
)
async def enrich_community(
    community_id: UUID,
    payload: CommunityEnrichRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CommunityEnrichResponse:
    service = IntelligenceService(session)
    try:
        result = await service.enrich_community(
            owner_id=user.id,
            parsed_chat_id=community_id,
            account_id=payload.account_id,
            member_limit=payload.member_limit,
            message_limit=payload.message_limit,
            lookback_days=payload.lookback_days,
            relevance_score=payload.relevance_score,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return CommunityEnrichResponse(**result)


@router.get("/audience", response_model=AudienceListResponse)
async def list_audience(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    platform: str | None = Query(default=None, max_length=32),
    min_activity_score: float | None = Query(default=None, ge=0, le=100),
    min_readiness_score: float | None = Query(default=None, ge=0, le=100),
    include_bots: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> AudienceListResponse:
    service = IntelligenceService(session)
    items, total = await service.list_audience(
        owner_id=user.id,
        platform=platform,
        min_activity_score=min_activity_score,
        min_readiness_score=min_readiness_score,
        include_bots=include_bots,
        skip=skip,
        limit=limit,
    )
    return AudienceListResponse(
        items=[AudienceMemberResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )
