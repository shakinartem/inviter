"""Proxies API — полный CRUD + тестирование + массовые операции + импорт."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import get_db_session
from app.core.security import get_current_active_user
from app.features.auth.models import User
from app.features.proxies.schemas import (
    BulkProxyCreate,
    BulkTestRequest,
    BulkTestResult,
    ProxyBulkCreateResult,
    ProxyCreate,
    ProxyListFilter,
    ProxyListItem,
    ProxyListResponse,
    ProxyResponse,
    ProxyStats,
    ProxyTestResult,
    ProxyTextImport,
    ProxyUpdate,
    ProxyWithAccounts,
)
from app.features.proxies.service import ProxyService

router = APIRouter(prefix="/proxies", tags=["Proxies"])

_LOGGER = logger.bind(module="proxies_api")


# --------------------------------------------------------------------------- #
# Dependency
# --------------------------------------------------------------------------- #
async def get_proxy_service(
    session: AsyncSession = Depends(get_db_session),
    redis: Optional[Redis] = Depends(get_redis),
) -> ProxyService:
    """Dependency для получения ProxyService."""
    return ProxyService(session=session, redis=redis)


# ================================================================== #
#   CREATE
# ================================================================== #


@router.post(
    "/",
    response_model=ProxyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать прокси",
    description="Создаёт новый прокси и запускает фоновую проверку.",
)
async def create_proxy(
    data: ProxyCreate,
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Создать один прокси-сервер."""
    proxy = await service.create_proxy(data=data, owner_id=current_user.id)

    log = _LOGGER.bind(proxy_id=str(proxy.id))
    log.info("Proxy created via API", scheme=proxy.scheme, host=proxy.host)

    return proxy


@router.post(
    "/bulk",
    response_model=ProxyBulkCreateResult,
    status_code=status.HTTP_201_CREATED,
    summary="Массовое создание прокси",
    description="Создаёт несколько прокси из списка. Каждый будет автоматически проверен.",
)
async def bulk_create_proxies(
    data: BulkProxyCreate,
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Массовое создание прокси из списка."""
    created = await service.bulk_create(data=data, owner_id=current_user.id)

    log = _LOGGER.bind(count=len(created))
    log.info("Bulk proxies created via API")

    return ProxyBulkCreateResult(
        created=[ProxyResponse.model_validate(p, from_attributes=True) for p in created],
        failed=[],
        total_requested=len(data.proxies),
        success_count=len(created),
        fail_count=0,
    )


@router.post(
    "/import",
    response_model=ProxyBulkCreateResult,
    status_code=status.HTTP_201_CREATED,
    summary="Импорт прокси из текста",
    description=(
        "Импорт прокси из текстового формата. "
        "Формат: scheme://user:password@host:port или host:port (построчно)."
    ),
)
async def import_proxies(
    data: ProxyTextImport,
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Импорт прокси из текста (CSV/построчный)."""
    created = await service.import_from_text(data=data, owner_id=current_user.id)

    log = _LOGGER.bind(count=len(created))
    log.info("Proxies imported via API")

    return ProxyBulkCreateResult(
        created=[ProxyResponse.model_validate(p, from_attributes=True) for p in created],
        failed=[],
        total_requested=len(data.text.strip().split("\n")),
        success_count=len(created),
        fail_count=0,
    )


# ================================================================== #
#   READ
# ================================================================== #


@router.get(
    "/",
    response_model=ProxyListResponse,
    summary="Список прокси",
    description="Получить список прокси с фильтрацией, поиском и пагинацией.",
)
async def list_proxies(
    scheme: Optional[str] = Query(default=None, description="Фильтр по типу (http/socks5/mtproto)"),
    is_active: Optional[bool] = Query(default=None, description="Фильтр по активности"),
    is_working: Optional[bool] = Query(default=None, description="Фильтр по работоспособности"),
    country: Optional[str] = Query(default=None, max_length=100, description="Фильтр по стране"),
    search: Optional[str] = Query(default=None, max_length=120, description="Поиск по title/host"),
    skip: int = Query(default=0, ge=0, description="Смещение"),
    limit: int = Query(default=50, ge=1, le=500, description="Размер страницы"),
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Список прокси с фильтрацией."""
    filters = ProxyListFilter(
        scheme=scheme,  # type: ignore[arg-type]
        is_active=is_active,
        is_working=is_working,
        country=country,
        search=search,
    )

    proxies, total = await service.list_proxies(
        owner_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
    )

    return ProxyListResponse(
        items=[ProxyListItem.model_validate(p, from_attributes=True) for p in proxies],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/working",
    response_model=list[ProxyListItem],
    summary="Рабочие прокси",
    description="Получить список подтверждённо рабочих прокси (с Redis-кэшем).",
)
async def get_working_proxies(
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Только рабочие прокси."""
    proxies = await service.get_working_proxies(owner_id=current_user.id)
    return [ProxyListItem.model_validate(p, from_attributes=True) for p in proxies]


@router.get(
    "/stats",
    response_model=ProxyStats,
    summary="Статистика",
    description="Агрегированная статистика по всем прокси владельца.",
)
async def get_proxy_stats(
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Сводная статистика по прокси."""
    return await service.get_stats(owner_id=current_user.id)


@router.get(
    "/{proxy_id}",
    response_model=ProxyResponse,
    summary="Получить прокси",
    description="Детальная информация о прокси включая количество привязанных аккаунтов.",
)
async def get_proxy(
    proxy_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Получить прокси по ID."""
    proxy = await service.get_proxy(proxy_id=proxy_id, owner_id=current_user.id)
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy not found",
        )
    return ProxyResponse.model_validate(proxy, from_attributes=True)


@router.get(
    "/{proxy_id}/accounts",
    response_model=ProxyWithAccounts,
    summary="Прокси с аккаунтами",
    description="Получить прокси со списком привязанных аккаунтов.",
)
async def get_proxy_with_accounts(
    proxy_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Прокси со списком аккаунтов."""
    proxy = await service.get_proxy(proxy_id=proxy_id, owner_id=current_user.id)
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy not found",
        )

    from app.features.accounts.schemas import AccountListItem

    return ProxyWithAccounts(
        proxy=ProxyResponse.model_validate(proxy, from_attributes=True),
        accounts=[
            AccountListItem.model_validate(a, from_attributes=True)
            for a in (proxy.accounts or [])
        ],
    )


# ================================================================== #
#   UPDATE
# ================================================================== #


@router.patch(
    "/{proxy_id}",
    response_model=ProxyResponse,
    summary="Обновить прокси",
    description="Частичное обновление прокси. При изменении параметров подключения запускается перепроверка.",
)
async def update_proxy(
    proxy_id: UUID,
    data: ProxyUpdate,
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Обновить прокси."""
    proxy = await service.get_proxy(proxy_id=proxy_id, owner_id=current_user.id)
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy not found",
        )

    updated = await service.update_proxy(proxy=proxy, data=data)
    return ProxyResponse.model_validate(updated, from_attributes=True)


# ================================================================== #
#   DELETE
# ================================================================== #


@router.delete(
    "/{proxy_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить прокси",
    description="Удаляет прокси. Нельзя удалить, если есть активные аккаунты, использующие его.",
)
async def delete_proxy(
    proxy_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Удалить прокси."""
    proxy = await service.get_proxy(proxy_id=proxy_id, owner_id=current_user.id)
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy not found",
        )

    try:
        await service.delete_proxy(proxy=proxy)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return {"status": "deleted", "proxy_id": str(proxy_id)}


# ================================================================== #
#   TEST
# ================================================================== #


@router.post(
    "/test",
    response_model=ProxyTestResult,
    summary="Тест прокси (без сохранения)",
    description="Проверить произвольный прокси по host:port без создания в БД.",
)
async def test_proxy_raw(
    host: str = Query(..., description="Хост прокси"),
    port: int = Query(..., ge=1, le=65535, description="Порт прокси"),
    scheme: str = Query(default="socks5", description="Тип прокси"),
    username: Optional[str] = Query(default=None, description="Имя пользователя"),
    password: Optional[str] = Query(default=None, description="Пароль"),
    secret: Optional[str] = Query(default=None, description="Секрет MTProto"),
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Проверить произвольный прокси (без сохранения в БД)."""
    result = await service.test_proxy(
        proxy=None,
        host=host,
        port=port,
        scheme=scheme,
        username=username,
        password=password,
        secret=secret,
    )
    return result


@router.post(
    "/{proxy_id}/test",
    response_model=ProxyTestResult,
    summary="Проверить сохранённый прокси",
    description="Тест существующего прокси из БД с обновлением статуса.",
)
async def test_proxy_by_id(
    proxy_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Проверить прокси из БД и обновить его статус."""
    proxy = await service.get_proxy(proxy_id=proxy_id, owner_id=current_user.id)
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy not found",
        )

    result = await service.test_proxy(proxy=proxy)
    return result


@router.post(
    "/bulk-test",
    response_model=BulkTestResult,
    summary="Массовое тестирование",
    description="Массовая проверка нескольких прокси (до 100 шт).",
)
async def bulk_test_proxies(
    data: BulkTestRequest,
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Массовое тестирование прокси."""
    # Проверяем, что все прокси принадлежат пользователю
    for proxy_id in data.proxy_ids:
        proxy = await service.get_proxy(proxy_id=proxy_id, owner_id=current_user.id)
        if not proxy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proxy {proxy_id} not found or not owned by you",
            )

    results = await service.test_bulk(proxy_ids=data.proxy_ids)

    return BulkTestResult(
        results=results,
        total=len(results),
        success_count=sum(1 for r in results if r.is_working),
        fail_count=sum(1 for r in results if not r.is_working),
    )


# ================================================================== #
#   CACHE
# ================================================================== #


@router.post(
    "/cache/invalidate",
    status_code=status.HTTP_200_OK,
    summary="Сбросить кэш",
    description="Инвалидировать Redis-кэш рабочих прокси.",
)
async def invalidate_cache(
    current_user: User = Depends(get_current_active_user),
    service: ProxyService = Depends(get_proxy_service),
):
    """Сбросить кэш рабочих прокси."""
    await service.invalidate_cache()
    return {"status": "cache_invalidated"}