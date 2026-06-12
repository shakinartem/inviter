"""
API-эндпоинты модуля parser — парсер чатов и пользователей по нише.

Содержит:
- POST   /parse            — запуск парсинга
- GET    /chats            — список спарсенных чатов с фильтрами
- GET    /chats/{id}       — детальная информация о чате
- DELETE /chats/{id}       — удаление чата
- POST   /chats/bulk-delete — массовое удаление
- GET    /stats            — сводная статистика
- GET    /export           — экспорт в CSV
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.security import get_current_active_user as current_user
from app.features.parser.models import ParsedChat as ParsedChatModel
from app.features.parser.schemas import (
    BulkParseRequest,
    ParsedChatCreate,
    ParsedChatListItem,
    ParsedChatListResponse,
    ParsedChatResponse,
    ParserSearchRequest,
    ParserStats,
)
from app.features.parser.service import ParserService

# ==================== Router ====================

router = APIRouter(prefix="/parser", tags=["parser"])


# ==================== Dependencies ====================


async def get_parser_service(request: Request) -> ParserService:
    """Получить экземпляр ParserService из состояния приложения (или создать)."""
    if not hasattr(request.app.state, "parser_service"):
        redis = getattr(request.app.state, "redis", None)
        request.app.state.parser_service = ParserService(redis=redis)
    return request.app.state.parser_service


# ==================== POST /parse ====================


@router.post(
    "/parse",
    response_model=list[ParsedChatResponse],
    status_code=status.HTTP_200_OK,
    summary="Запуск парсинга чатов",
    description="Запускает парсинг чатов по заданному запросу и источнику (Telegram, TGStat). "
    "Результаты сохраняются в БД с дедупликацией.",
)
async def parse_chats(
    request: ParserSearchRequest,
    user: Any = Depends(current_user),
    parser_service: ParserService = Depends(get_parser_service),
    db_session: AsyncSession = Depends(get_db_session),
) -> list[ParsedChatResponse]:
    """Запустить парсинг чатов по нише."""
    log = logger.bind(
        user_id=str(user.id),
        query=request.query,
        source=request.source,
    )
    log.info("POST /parse called")

    try:
        chats = await parser_service.search_chats(
            request=request,
            owner_id=user.id,
            db_session=db_session,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        log.error("Parse failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parse failed: {str(exc)[:500]}",
        )

    return [ParsedChatResponse.model_validate(chat) for chat in chats]


# ==================== POST /chats/bulk-parse ====================


@router.post(
    "/chats/bulk-parse",
    response_model=list[ParsedChatResponse],
    status_code=status.HTTP_200_OK,
    summary="Массовый парсинг чатов",
)
async def bulk_parse_chats(
    request: BulkParseRequest,
    user: Any = Depends(current_user),
    parser_service: ParserService = Depends(get_parser_service),
    db_session: AsyncSession = Depends(get_db_session),
) -> list[ParsedChatResponse]:
    """Массовый парсинг по нескольким запросам с дедупликацией."""
    log = logger.bind(user_id=str(user.id), count=len(request.requests))
    log.info("POST /chats/bulk-parse called")

    all_chats: list[ParsedChatModel] = []
    seen_chat_ids: set[int] = set()

    for req in request.requests:
        try:
            chats = await parser_service.search_chats(
                request=req,
                owner_id=user.id,
                db_session=db_session,
            )
            for chat in chats:
                if chat.chat_id not in seen_chat_ids:
                    all_chats.append(chat)
                    seen_chat_ids.add(chat.chat_id)
                elif not request.deduplicate:
                    all_chats.append(chat)
        except Exception as exc:
            log.warning(
                "Bulk parse sub-request failed",
                query=req.query,
                error=str(exc)[:200],
            )
            continue

    return [ParsedChatResponse.model_validate(chat) for chat in all_chats]


# ==================== POST /chats ====================


@router.post(
    "/chats",
    response_model=ParsedChatResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ручное добавление чата",
)
async def create_chat(
    chat_data: ParsedChatCreate,
    user: Any = Depends(current_user),
    parser_service: ParserService = Depends(get_parser_service),
    db_session: AsyncSession = Depends(get_db_session),
) -> ParsedChatResponse:
    """Ручное добавление спарсенного чата в БД."""
    log = logger.bind(user_id=str(user.id), chat_id=chat_data.chat_id)
    log.info("POST /chats called")

    saved = await parser_service.save_parsed_chats(
        chats=[chat_data],
        owner_id=user.id,
        db_session=db_session,
    )
    if not saved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to save chat",
        )

    return ParsedChatResponse.model_validate(saved[0])


# ==================== GET /chats ====================


@router.get(
    "/chats",
    response_model=ParsedChatListResponse,
    summary="Список спарсенных чатов",
)
async def list_chats(
    request: Request,
    user: Any = Depends(current_user),
    parser_service: ParserService = Depends(get_parser_service),
    db_session: AsyncSession = Depends(get_db_session),
    skip: int = Query(default=0, ge=0, description="Смещение"),
    limit: int = Query(default=50, ge=1, le=1000, description="Размер страницы"),
    source: Optional[str] = Query(default=None, description="Фильтр по источнику"),
    category: Optional[str] = Query(default=None, description="Фильтр по категории"),
    niche: Optional[str] = Query(default=None, description="Фильтр по нише"),
    language: Optional[str] = Query(default=None, description="Фильтр по языку"),
    chat_type: Optional[str] = Query(default=None, description="Фильтр по типу чата"),
    search: Optional[str] = Query(default=None, description="Поиск по названию/username"),
    is_active: Optional[bool] = Query(default=None, description="Только активные"),
) -> ParsedChatListResponse:
    """Получить список спарсенных чатов с фильтрацией и пагинацией."""
    log = logger.bind(user_id=str(user.id))
    log.info("GET /chats called", skip=skip, limit=limit)

    filters: dict[str, Any] = {}
    if source:
        filters["source"] = source
    if category:
        filters["category"] = category
    if niche:
        filters["niche"] = niche
    if language:
        filters["language"] = language
    if chat_type:
        filters["chat_type"] = chat_type
    if search:
        filters["search"] = search
    if is_active is not None:
        filters["is_active"] = is_active

    chats, total = await parser_service.list_chats(
        owner_id=user.id,
        skip=skip,
        limit=limit,
        filters=filters if filters else None,
        db_session=db_session,
    )

    return ParsedChatListResponse(
        items=[ParsedChatListItem.model_validate(chat) for chat in chats],
        total=total,
        skip=skip,
        limit=limit,
    )


# ==================== GET /chats/{id} ====================


@router.get(
    "/chats/{chat_id}",
    response_model=ParsedChatResponse,
    summary="Детальная информация о чате",
)
async def get_chat(
    chat_id: UUID,
    user: Any = Depends(current_user),
    parser_service: ParserService = Depends(get_parser_service),
    db_session: AsyncSession = Depends(get_db_session),
) -> ParsedChatResponse:
    """Получить детальную информацию о спарсенном чате."""
    chat = await parser_service.get_chat_by_id(
        chat_id=chat_id,
        owner_id=user.id,
        db_session=db_session,
    )
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    return ParsedChatResponse.model_validate(chat)


# ==================== DELETE /chats/{id} ====================


@router.delete(
    "/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удаление чата",
)
async def delete_chat(
    chat_id: UUID,
    user: Any = Depends(current_user),
    parser_service: ParserService = Depends(get_parser_service),
    db_session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Удалить спарсенный чат по UUID."""
    deleted = await parser_service.delete_chat(
        chat_id=chat_id,
        owner_id=user.id,
        db_session=db_session,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==================== POST /chats/bulk-delete ====================


@router.post(
    "/chats/bulk-delete",
    status_code=status.HTTP_200_OK,
    summary="Массовое удаление чатов",
)
async def bulk_delete_chats(
    request: Request,
    user: Any = Depends(current_user),
    parser_service: ParserService = Depends(get_parser_service),
    db_session: AsyncSession = Depends(get_db_session),
    chat_ids: list[UUID] = Query(..., description="Список UUID чатов для удаления"),
) -> dict[str, Any]:
    """Массовое удаление спарсенных чатов по списку ID."""
    if not chat_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chat_ids list is empty",
        )

    deleted = await parser_service.bulk_delete_chats(
        chat_ids=chat_ids,
        owner_id=user.id,
        db_session=db_session,
    )

    return {
        "deleted_count": deleted,
        "total_requested": len(chat_ids),
    }


# ==================== GET /stats ====================


@router.get(
    "/stats",
    response_model=ParserStats,
    summary="Сводная статистика",
)
async def get_stats(
    user: Any = Depends(current_user),
    parser_service: ParserService = Depends(get_parser_service),
    db_session: AsyncSession = Depends(get_db_session),
) -> ParserStats:
    """Получить сводную статистику по спарсенным чатам пользователя."""
    log = logger.bind(user_id=str(user.id))
    log.info("GET /stats called")

    stats = await parser_service.get_stats(
        owner_id=user.id,
        db_session=db_session,
    )
    return stats


# ==================== GET /export ====================


@router.get(
    "/export",
    response_class=PlainTextResponse,
    summary="Экспорт чатов в CSV",
    responses={
        200: {
            "content": {"text/csv": {}},
            "description": "CSV-файл со списком чатов",
        },
    },
)
async def export_chats(
    user: Any = Depends(current_user),
    parser_service: ParserService = Depends(get_parser_service),
    db_session: AsyncSession = Depends(get_db_session),
    category: Optional[str] = Query(default=None),
    niche: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    language: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
) -> PlainTextResponse:
    """Экспортировать спарсенные чаты в CSV."""
    log = logger.bind(user_id=str(user.id))
    log.info("GET /export called")

    filters: dict[str, Any] = {}
    if category:
        filters["category"] = category
    if niche:
        filters["niche"] = niche
    if source:
        filters["source"] = source
    if language:
        filters["language"] = language
    if is_active is not None:
        filters["is_active"] = is_active

    csv_content = await parser_service.export_chats_to_csv(
        owner_id=user.id,
        filters=filters if filters else None,
        db_session=db_session,
    )

    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=parsed_chats.csv",
        },
    )
