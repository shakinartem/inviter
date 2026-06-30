"""
API endpoints for Source Discovery (TGStat keyword discovery).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.auth.models import User
from app.features.source_discovery.schemas import (
    AnalysisResult,
    SelectResult,
    SourceCandidateListResponse,
    SourceCandidateListItem,
    SourceCandidateResponse,
    SourceDiscoverySearchRequest,
    SourceScoreResponse,
)
from app.features.source_discovery.service import TgstatDiscoveryService

router = APIRouter(prefix="/source-discovery", tags=["Source Discovery"])

_LOGGER = logger.bind(module="source_discovery_api")

# Singleton service instance
_discovery_service: Optional[TgstatDiscoveryService] = None


def get_discovery_service() -> TgstatDiscoveryService:
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = TgstatDiscoveryService()
    return _discovery_service


# ==================== Search ====================


@router.post(
    "/tgstat/search",
    response_model=list[SourceCandidateListItem],
    summary="Search TGStat by keyword",
    description="Search Telegram channels/chats on TGStat by keyword query.",
)
async def search_tgstat(
    body: SourceDiscoverySearchRequest,
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Search TGStat for sources matching the keyword query."""
    service = get_discovery_service()

    try:
        candidates = await service.search_sources(
            request=body,
            owner_id=current_user.id,
            db_session=db_session,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        _LOGGER.error("TGStat search failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(exc)[:500]}",
        )

    items = []
    for c in candidates:
        best_score = None
        if c.scores:
            best_score = max(s.total_score for s in c.scores)
        items.append(
            SourceCandidateListItem(
                id=c.id,
                source_type=c.source_type,
                title=c.title,
                username=c.username,
                url=c.url,
                tgstat_url=c.tgstat_url,
                category=c.category,
                subscribers_count=c.subscribers_count,
                status=c.status,
                total_score=best_score,
                discovered_by_query=c.discovered_by_query,
                discovered_at=c.discovered_at,
                created_at=c.created_at,
            )
        )

    return items


# ==================== List ====================


@router.get(
    "/sources",
    response_model=SourceCandidateListResponse,
    summary="List source candidates",
)
async def list_sources(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """List discovered source candidates."""
    service = get_discovery_service()
    items, total = await service.list_sources(
        owner_id=current_user.id,
        skip=skip,
        limit=limit,
        status=status,
        db_session=db_session,
    )
    return SourceCandidateListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


# ==================== Get ====================


@router.get(
    "/sources/{source_id}",
    response_model=SourceCandidateResponse,
    summary="Get source candidate details",
)
async def get_source(
    source_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get detailed info about a source candidate."""
    from app.features.source_discovery.models import SourceCandidate

    result = await db_session.execute(
        select(SourceCandidate).where(
            SourceCandidate.id == source_id,
            SourceCandidate.owner_id == current_user.id,
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    return SourceCandidateResponse.model_validate(candidate)


# ==================== Analyze ====================


@router.post(
    "/sources/{source_id}/analyze",
    response_model=AnalysisResult,
    summary="Analyze source candidate",
    description="Fetch detailed metrics from TGStat and calculate quality scores.",
)
async def analyze_source(
    source_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Analyze a source candidate and calculate scores."""
    service = get_discovery_service()

    try:
        score = await service.analyze_source(
            candidate_id=source_id,
            owner_id=current_user.id,
            db_session=db_session,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        _LOGGER.error("Analysis failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(exc)[:500]}",
        )

    # Get updated candidate
    from app.features.source_discovery.models import SourceCandidate

    result = await db_session.execute(
        select(SourceCandidate).where(SourceCandidate.id == source_id)
    )
    candidate = result.scalar_one()

    return AnalysisResult(
        candidate=SourceCandidateResponse.model_validate(candidate),
        score=SourceScoreResponse.model_validate(score),
    )


# ==================== Select ====================


@router.post(
    "/sources/{source_id}/select",
    response_model=SelectResult,
    summary="Select source for campaign",
)
async def select_source(
    source_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Mark source as selected for campaign use."""
    service = get_discovery_service()

    try:
        candidate = await service.select_source(
            candidate_id=source_id,
            owner_id=current_user.id,
            db_session=db_session,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return SelectResult(
        candidate_id=source_id,
        status="selected",
        message=f"Source '{candidate.title or candidate.username}' selected for campaign.",
    )


# ==================== Reject ====================


@router.post(
    "/sources/{source_id}/reject",
    response_model=dict,
    summary="Reject source candidate",
)
async def reject_source(
    source_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Mark source as rejected."""
    service = get_discovery_service()

    try:
        await service.reject_source(
            candidate_id=source_id,
            owner_id=current_user.id,
            db_session=db_session,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return {"status": "rejected", "source_id": str(source_id)}


# ==================== Delete ====================


@router.delete(
    "/sources/{source_id}",
    response_model=dict,
    summary="Delete source candidate",
)
async def delete_source(
    source_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Delete a source candidate."""
    service = get_discovery_service()

    try:
        await service.delete_source(
            candidate_id=source_id,
            owner_id=current_user.id,
            db_session=db_session,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return {"status": "deleted", "source_id": str(source_id)}