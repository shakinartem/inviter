from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.intelligence.intent_schemas import (
    IntentScanRequest,
    IntentScanResponse,
    IntentSignalResponse,
)
from app.features.intelligence.intent_service import IntentSignalService


router = APIRouter(prefix="/intelligence/intent", tags=["intent"])


@router.post(
    "/communities/{community_id}/scan",
    response_model=IntentScanResponse,
)
async def scan_community_intent(
    community_id: UUID,
    payload: IntentScanRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> IntentScanResponse:
    service = IntentSignalService(session)
    try:
        result = await service.scan_community(
            owner_id=user.id,
            parsed_chat_id=community_id,
            account_id=payload.account_id,
            lookback_days=payload.lookback_days,
            message_limit=payload.message_limit,
            minimum_score=payload.minimum_score,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return IntentScanResponse(**result)


@router.get("/signals", response_model=list[IntentSignalResponse])
async def list_intent_signals(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    audience_member_id: UUID | None = Query(default=None),
    community_id: UUID | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[IntentSignalResponse]:
    service = IntentSignalService(session)
    signals = await service.list_signals(
        owner_id=user.id,
        audience_member_id=audience_member_id,
        parsed_chat_id=community_id,
        min_score=min_score,
        limit=limit,
    )
    return [IntentSignalResponse.model_validate(signal) for signal in signals]
