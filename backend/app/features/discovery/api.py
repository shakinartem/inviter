from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.discovery.platform_service import PlatformDiscoveryService
from app.features.discovery.schemas import PlatformDiscoveryRequest
from app.features.discovery.service import DiscoveryService
from app.features.parser.schemas import ParsedChatResponse, ParserSearchRequest


router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/search", response_model=list[ParsedChatResponse])
async def search_communities(
    payload: ParserSearchRequest,
    request: Request,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ParsedChatResponse]:
    service = DiscoveryService(
        session,
        redis=getattr(request.app.state, "redis", None),
    )
    try:
        chats = await service.search(request=payload, owner_id=user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    finally:
        await service.close()

    return [ParsedChatResponse.model_validate(chat) for chat in chats]


@router.post(
    "/platforms/{platform}/search",
    response_model=list[ParsedChatResponse],
)
async def search_platform_communities(
    platform: str,
    payload: PlatformDiscoveryRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ParsedChatResponse]:
    service = PlatformDiscoveryService(session)
    try:
        chats = await service.search(
            owner_id=user.id,
            platform=platform,
            query=payload.query,
            account_id=payload.account_id,
            limit=payload.limit,
            chat_type=payload.chat_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return [ParsedChatResponse.model_validate(chat) for chat in chats]
