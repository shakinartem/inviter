from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.segments.preview import SegmentPreviewService
from app.features.segments.preview_schemas import SegmentPreviewRequest, SegmentPreviewResponse


router = APIRouter(prefix="/segments", tags=["segments"])


@router.post("/preview", response_model=SegmentPreviewResponse)
async def preview_segment(
    payload: SegmentPreviewRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SegmentPreviewResponse:
    try:
        result = await SegmentPreviewService(session).preview(user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SegmentPreviewResponse(**result)
