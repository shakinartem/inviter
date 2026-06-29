"""
API endpoints для ProxyCandidate.

Эндпоинты (только для superuser/admin):
- POST /proxy-candidates/import-mtproto-text — импорт MTProto из текста
- POST /proxy-candidates/import-text — импорт обычных прокси из текста
- GET /proxy-candidates — список кандидатов
- GET /proxy-candidates/{id} — детально кандидата
- POST /proxy-candidates/{id}/check — проверка кандидата
- POST /proxy-candidates/bulk-check — массовая проверка
- POST /proxy-candidates/{id}/approve — одобрение кандидата
- POST /proxy-candidates/{id}/reject — отклонение кандидата
- DELETE /proxy-candidates/{id} — удаление кандидата

READ endpoints доступны авторизованным пользователям.
WRITE/IMPORT/APPROVE — только superuser/admin.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, get_current_superuser
from app.db.session import get_db_session
from app.features.auth.models import User
from app.features.proxies.candidate_schemas import (
    BulkCheckRequest,
    CandidateListItem,
    CandidateListResponse,
    CandidateResponse,
    MtprotoImportRequest,
    MtprotoImportResult,
    TextImportRequest,
    TextImportResult,
)
from app.features.proxies.candidate_service import CandidateService
from app.features.proxies.schemas import ProxyTestResult

router = APIRouter(prefix="/proxy-candidates", tags=["Proxy Candidates"])

_LOGGER = logger.bind(module="candidate_api")


# --------------------------------------------------------------------------- #
# Dependency
# --------------------------------------------------------------------------- #
async def get_candidate_service(
    session: AsyncSession = Depends(get_db_session),
) -> CandidateService:
    """Dependency для получения CandidateService."""
    return CandidateService(session=session)


# ================================================================== #
#   IMPORT MTProto
# ================================================================== #


@router.post(
    "/import-mtproto-text",
    response_model=MtprotoImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="Импорт MTProto-прокси из текста",
    description=(
        "Парсит MTProto-ссылки из текста, создаёт кандидатов. "
        "Только для superuser/admin."
    ),
)
async def import_mtproto_from_text(
    data: MtprotoImportRequest,
    current_user: User = Depends(get_current_superuser),
    service: CandidateService = Depends(get_candidate_service),
):
    """Импорт MTProto-прокси из текста (superuser/admin)."""
    result = await service.import_mtproto_from_text(
        text=data.text,
        owner_id=current_user.id,
        source_name=data.source_name,
        source_type="mtproto_text",
    )

    _LOGGER.info(
        "MTProto import via API",
        imported=result.imported_count,
        skipped=result.skipped_duplicates,
        invalid=result.invalid_count,
    )

    return result


# ================================================================== #
#   IMPORT Text (socks5, http)
# ================================================================== #


@router.post(
    "/import-text",
    response_model=TextImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="Импорт прокси из текста",
    description=(
        "Парсит обычные прокси (socks5, http) из текста, создаёт кандидатов. "
        "Только для superuser/admin."
    ),
)
async def import_text(
    data: TextImportRequest,
    current_user: User = Depends(get_current_superuser),
    service: CandidateService = Depends(get_candidate_service),
):
    """Импорт обычных прокси из текста (superuser/admin)."""
    result = await service.import_text(
        text=data.text,
        owner_id=current_user.id,
        source_name=data.source_name,
        source_type="manual_text",
    )

    _LOGGER.info(
        "Text proxy import via API",
        imported=result.imported_count,
        skipped=result.skipped_duplicates,
        invalid=result.invalid_count,
    )

    return result


# ================================================================== #
#   LIST
# ================================================================== #


@router.get(
    "/",
    response_model=CandidateListResponse,
    summary="Список кандидатов",
    description="Получить список кандидатов с фильтрацией и пагинацией.",
)
async def list_candidates(
    proxy_type: Optional[str] = Query(default=None, description="Фильтр по типу (mtproto, socks5, http)"),
    status: Optional[str] = Query(default=None, description="Фильтр по статусу"),
    skip: int = Query(default=0, ge=0, description="Смещение"),
    limit: int = Query(default=50, ge=1, le=500, description="Размер страницы"),
    current_user: User = Depends(get_current_active_user),
    service: CandidateService = Depends(get_candidate_service),
):
    """Список кандидатов (для авторизованных пользователей)."""
    candidates, total = await service.list_candidates(
        owner_id=current_user.id,
        proxy_type=proxy_type,
        status=status,
        skip=skip,
        limit=limit,
    )

    return CandidateListResponse(
        items=[
            CandidateListItem.from_orm_with_masked_secrets(c)
            for c in candidates
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


# ================================================================== #
#   GET
# ================================================================== #


@router.get(
    "/{candidate_id}",
    response_model=CandidateResponse,
    summary="Получить кандидата",
    description="Детальная информация о кандидате (secret/password замаскированы).",
)
async def get_candidate(
    candidate_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: CandidateService = Depends(get_candidate_service),
):
    """Получить кандидата по ID."""
    candidate = await service.get_candidate(
        candidate_id=candidate_id,
        owner_id=current_user.id,
    )
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return CandidateResponse.from_orm_with_masked_secrets(candidate)


# ================================================================== #
#   CHECK
# ================================================================== #


@router.post(
    "/{candidate_id}/check",
    response_model=ProxyTestResult,
    summary="Проверить кандидата",
    description=(
        "Проверить кандидата (TCP connect). "
        "Только для superuser/admin."
    ),
)
async def check_candidate(
    candidate_id: UUID,
    current_user: User = Depends(get_current_superuser),
    service: CandidateService = Depends(get_candidate_service),
):
    """Проверить кандидата (superuser/admin)."""
    candidate = await service.get_candidate(
        candidate_id=candidate_id,
        owner_id=current_user.id,
    )
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    try:
        result = await service.check_candidate_by_id(candidate_id, current_user.id)
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        _LOGGER.error("Check failed", candidate_id=str(candidate_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Check failed: {exc}",
        )


@router.post(
    "/bulk-check",
    response_model=list[ProxyTestResult],
    summary="Массовая проверка кандидатов",
    description=(
        "Проверить несколько кандидатов (макс. 50). "
        "Только для superuser/admin."
    ),
)
async def bulk_check_candidates(
    data: BulkCheckRequest,
    current_user: User = Depends(get_current_superuser),
    service: CandidateService = Depends(get_candidate_service),
):
    """Массовая проверка кандидатов (superuser/admin)."""
    try:
        results = await service.bulk_check_candidates(
            ids=data.ids,
            owner_id=current_user.id,
        )
        return results
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        _LOGGER.error("Bulk check failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk check failed: {exc}",
        )


# ================================================================== #
#   APPROVE
# ================================================================== #


@router.post(
    "/{candidate_id}/approve",
    response_model=dict,
    summary="Одобрить кандидата",
    description=(
        "Одобрить кандидата и создать рабочий Proxy. "
        "Только для superuser/admin."
    ),
)
async def approve_candidate(
    candidate_id: UUID,
    current_user: User = Depends(get_current_superuser),
    service: CandidateService = Depends(get_candidate_service),
):
    """Одобрить кандидата (superuser/admin)."""
    candidate = await service.get_candidate(
        candidate_id=candidate_id,
        owner_id=current_user.id,
    )
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    try:
        proxy = await service.approve_candidate(
            candidate=candidate,
            owner_id=current_user.id,
        )
        return {
            "status": "approved",
            "candidate_id": str(candidate_id),
            "proxy_id": str(proxy.id),
            "proxy_title": proxy.title,
            "proxy_scheme": proxy.scheme,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except Exception as exc:
        _LOGGER.error("Approve failed", candidate_id=str(candidate_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approve failed: {exc}",
        )


# ================================================================== #
#   REJECT
# ================================================================== #


@router.post(
    "/{candidate_id}/reject",
    response_model=dict,
    summary="Отклонить кандидата",
    description="Отклонить кандидата (status=rejected). Только для superuser/admin.",
)
async def reject_candidate(
    candidate_id: UUID,
    current_user: User = Depends(get_current_superuser),
    service: CandidateService = Depends(get_candidate_service),
):
    """Отклонить кандидата (superuser/admin)."""
    candidate = await service.get_candidate(
        candidate_id=candidate_id,
        owner_id=current_user.id,
    )
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    try:
        await service.reject_candidate(candidate)
        return {"status": "rejected", "candidate_id": str(candidate_id)}
    except Exception as exc:
        _LOGGER.error("Reject failed", candidate_id=str(candidate_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reject failed: {exc}",
        )


# ================================================================== #
#   DELETE
# ================================================================== #


@router.delete(
    "/{candidate_id}",
    response_model=dict,
    summary="Удалить кандидата",
    description="Удалить кандидата. Только для superuser/admin.",
)
async def delete_candidate(
    candidate_id: UUID,
    current_user: User = Depends(get_current_superuser),
    service: CandidateService = Depends(get_candidate_service),
):
    """Удалить кандидата (superuser/admin)."""
    candidate = await service.get_candidate(
        candidate_id=candidate_id,
        owner_id=current_user.id,
    )
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    try:
        await service.delete_candidate(candidate)
        return {"status": "deleted", "candidate_id": str(candidate_id)}
    except Exception as exc:
        _LOGGER.error("Delete failed", candidate_id=str(candidate_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete failed: {exc}",
        )