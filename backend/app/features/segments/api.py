from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.segments.schemas import (
    SegmentCreate,
    SegmentMemberListResponse,
    SegmentMemberResponse,
    SegmentRefreshResponse,
    SegmentResponse,
    SegmentUpdate,
)
from app.features.segments.service import SegmentService


router = APIRouter(prefix="/segments", tags=["segments"])


@router.post("", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
async def create_segment(
    payload: SegmentCreate,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SegmentResponse:
    service = SegmentService(session)
    try:
        segment = await service.create(user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SegmentResponse.model_validate(segment)


@router.get("", response_model=list[SegmentResponse])
async def list_segments(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    active_only: bool | None = Query(default=None),
    platform: str | None = Query(default=None, max_length=32),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SegmentResponse]:
    items, _total = await SegmentService(session).list(
        user.id,
        active_only=active_only,
        platform=platform,
        skip=skip,
        limit=limit,
    )
    return [SegmentResponse.model_validate(item) for item in items]


@router.get("/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    segment_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SegmentResponse:
    segment = await SegmentService(session).get(user.id, segment_id)
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    return SegmentResponse.model_validate(segment)


@router.patch("/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    segment_id: UUID,
    payload: SegmentUpdate,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SegmentResponse:
    service = SegmentService(session)
    try:
        segment = await service.update(user.id, segment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    return SegmentResponse.model_validate(segment)


@router.post("/{segment_id}/refresh", response_model=SegmentRefreshResponse)
async def refresh_segment(
    segment_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SegmentRefreshResponse:
    try:
        result = await SegmentService(session).refresh(user.id, segment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SegmentRefreshResponse(**result)


@router.get("/{segment_id}/members", response_model=SegmentMemberListResponse)
async def segment_members(
    segment_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> SegmentMemberListResponse:
    try:
        items, total = await SegmentService(session).list_members(
            user.id,
            segment_id,
            skip=skip,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SegmentMemberListResponse(
        items=[SegmentMemberResponse(**item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.delete("/{segment_id}")
async def deactivate_segment(
    segment_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    segment = await SegmentService(session).update(
        user.id,
        segment_id,
        SegmentUpdate(is_active=False),
    )
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    return {"success": True}
