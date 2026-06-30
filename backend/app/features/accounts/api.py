from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.redis import get_redis
from app.db.session import get_db_session
from app.features.accounts.client_manager import TelegramClientManager
from app.features.accounts.models import Account
from app.features.accounts.schemas import (
    AccountCheckResponse,
    AccountCreate,
    AccountListFilter,
    AccountListItem,
    AccountResponse,
    AccountStats,
    AccountStatusUpdate,
    AccountUpdate,
    AuthConfirmRequest,
    AuthConfirmResponse,
    AuthStartResponse,
    SessionUploadResult,
)
from app.features.accounts.service import AccountService
from app.features.auth.models import User


router = APIRouter(prefix="/accounts", tags=["Accounts"])


# ==================== Schemas для bulk-операций ====================


class BulkStatusUpdateRequest(BaseModel):
    """Запрос на массовое обновление статуса."""
    account_ids: List[UUID] = Field(..., min_length=1, max_length=500)
    status: str = Field(..., description="Новый статус")
    status_message: Optional[str] = Field(default=None, max_length=500)


class BulkOperationResponse(BaseModel):
    """Результат массовой операции."""
    affected: int
    message: str


class CanInviteResponse(BaseModel):
    """Может ли аккаунт отправить инвайт."""
    account_id: UUID
    can_invite: bool
    reason: Optional[str] = None
    today_invites: int
    floodwait_remaining: int
    cooldown_until: Optional[str] = None
    banned_until: Optional[str] = None


class DetailedStatsResponse(BaseModel):
    """Подробная статистика по аккаунту."""
    account_id: str
    status: str
    is_active: bool
    is_premium: bool
    daily_invite_count: int
    total_invites: int
    total_invite_errors: int
    total_floodwaits: int
    success_rate: float
    floodwait_remaining: int
    last_used_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    cooldown_until: Optional[str] = None
    banned_until: Optional[str] = None
    session_exists: bool
    session_size: Optional[int] = None


class HealthResponse(BaseModel):
    """Health check для пула клиентов."""
    total_cached: int
    connected: int
    disconnected: int
    sessions_dir: str
    redis_enabled: bool


# ==================== Dependency ====================


async def get_service(
    session: AsyncSession = Depends(get_db_session),
) -> AccountService:
    """Получить AccountService со всеми зависимостями (Redis, ClientManager)."""
    redis = None
    try:
        redis = await get_redis()
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
    client_manager = TelegramClientManager(redis=redis)
    return AccountService(session=session, redis=redis, client_manager=client_manager)


def _ensure_owner(account: Account, user: User) -> None:
    """Проверить, что аккаунт принадлежит пользователю."""
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    if account.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )


# ==================== CRUD endpoints ====================


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account_in: AccountCreate,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """Создать запись о новом аккаунте. .session файл загружается отдельно."""
    try:
        account = await service.create_account(current_user.id, account_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    return account


@router.get("/", response_model=List[AccountListItem])
async def list_accounts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    filters: AccountListFilter = Depends(),
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """Список аккаунтов владельца с фильтрами и пагинацией."""
    accounts = await service.list_accounts(
        owner_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
    )
    return accounts


@router.get("/stats", response_model=AccountStats)
async def get_stats(
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """Сводная статистика по аккаунтам владельца."""
    return await service.get_stats(current_user.id)


@router.get("/health", response_model=HealthResponse)
async def get_pool_health(
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """Health-check пула Telegram-клиентов (для отладки/мониторинга)."""
    health = service.client_manager.get_health_stats()
    return HealthResponse(**health)


@router.get("/available", response_model=List[AccountListItem])
async def get_available_for_invite(
    daily_limit: int = Query(30, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """Список аккаунтов, которые МОГУТ инвайтить прямо сейчас."""
    accounts = await service.get_available_for_invite(
        owner_id=current_user.id, daily_limit=daily_limit
    )
    return accounts


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)
    return account


@router.get("/{account_id}/detailed-stats", response_model=DetailedStatsResponse)
async def get_detailed_stats(
    account_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """Подробная статистика по одному аккаунту (включая Redis)."""
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)
    stats = await service.get_detailed_stats(account_id)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    return DetailedStatsResponse(**stats)


@router.get("/{account_id}/can-invite", response_model=CanInviteResponse)
async def can_account_invite(
    account_id: UUID,
    daily_limit: int = Query(30, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """Проверить, может ли аккаунт отправить инвайт прямо сейчас."""
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)
    can, reason = await service.can_account_invite(account_id, daily_limit)
    today = await service.get_today_invites(account_id)
    floodwait_remaining = 0
    if service.redis is not None:
        floodwait_remaining = await service.client_manager.get_floodwait_remaining(
            account_id
        )
    return CanInviteResponse(
        account_id=account_id,
        can_invite=can,
        reason=reason,
        today_invites=today,
        floodwait_remaining=floodwait_remaining,
        cooldown_until=(
            account.cooldown_until.isoformat() if account.cooldown_until else None
        ),
        banned_until=(
            account.banned_until.isoformat() if account.banned_until else None
        ),
    )


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    account_in: AccountUpdate,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)
    updated = await service.update_account(account_id, account_in)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    return updated


@router.patch("/{account_id}/status", response_model=AccountResponse)
async def update_status(
    account_id: UUID,
    status_in: AccountStatusUpdate,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)
    updated = await service.update_status(account_id, status_in)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    # Если аккаунт перевели в active — инвалидируем клиент для пересоздания
    if status_in.status in ("active", "banned", "inactive"):
        await service.client_manager.invalidate_client(account_id)
    return updated


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)
    success = await service.delete_account(account_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    return None


# ==================== Session operations ====================


@router.post(
    "/{account_id}/upload-session",
    response_model=SessionUploadResult,
    status_code=status.HTTP_200_OK,
)
async def upload_session(
    account_id: UUID,
    file: UploadFile = File(..., description="Telethon .session file"),
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """
    Загрузить .session файл для аккаунта.
    Файл должен быть сгенерирован Telethon (sqlite3).
    """
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)

    try:
        session_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {e}",
        )

    try:
        await service.upload_session(account_id, session_bytes)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    size = len(session_bytes)
    logger.bind(
        account_id=str(account_id),
        session_name=account.session_name,
        size=size,
    ).info("Session uploaded")

    return SessionUploadResult(
        account_id=account.id,
        session_name=account.session_name,
        session_size=size,
        validated=True,
        message="Session file uploaded. Run /check to verify authorization.",
    )


@router.post("/{account_id}/check", response_model=AccountCheckResponse)
async def check_account(
    account_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """
    Проверить авторизацию аккаунта (client.get_me()).
    Обновляет профиль и метрики в БД.
    """
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)

    try:
        result = await service.check_account(account_id)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    return AccountCheckResponse(account_id=account_id, **result)


# ==================== Auth operations ====================


@router.post("/{account_id}/auth/start", response_model=AuthStartResponse)
async def auth_start(
    account_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """
    Начать авторизацию аккаунта в Telegram.
    Отправляет код подтверждения на номер телефона.
    """
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)

    try:
        result = await service.auth_start(account_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        logger.error("Auth start failed", account_id=str(account_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auth start failed: {str(e)[:500]}",
        )

    return AuthStartResponse(
        account_id=account_id,
        status="code_sent",
        phone_code_hash=result["phone_code_hash"],
        timeout=result.get("timeout", 30),
    )


@router.post("/{account_id}/auth/confirm", response_model=AuthConfirmResponse)
async def auth_confirm(
    account_id: UUID,
    body: AuthConfirmRequest,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """
    Подтвердить код авторизации.
    При необходимости ввести пароль 2FA.
    """
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)

    try:
        result = await service.auth_confirm(
            account_id=account_id,
            code=body.code,
            password=body.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        error_str = str(e)
        logger.error("Auth confirm failed", account_id=str(account_id), error=error_str)
        # Map common errors
        if "CODE_INVALID" in error_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid code. Please check the code and try again.",
            )
        if "PASSWORD_REQUIRED" in error_str or "SESSION_PASSWORD_NEEDED" in error_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PASSWORD_REQUIRED",
            )
        if "FLOOD_WAIT" in error_str:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait before trying again.",
            )
        if "PHONE_CODE_EXPIRED" in error_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code expired. Please start authorization again.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auth failed: {error_str[:500]}",
        )

    return AuthConfirmResponse(
        account_id=account_id,
        authorized=True,
        telegram_user_id=result.get("telegram_user_id"),
        username=result.get("username"),
        first_name=result.get("first_name"),
        last_name=result.get("last_name"),
        is_premium=result.get("is_premium", False),
        is_bot=result.get("is_bot", False),
        phone=result.get("phone"),
        status=result.get("status", "active"),
        status_message=result.get("status_message"),
    )


@router.post("/{account_id}/invalidate-client", status_code=status.HTTP_200_OK)
async def invalidate_client(
    account_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """Принудительно отключить и удалить клиент из пула."""
    account = await service.get_account(account_id)
    _ensure_owner(account, current_user)
    await service.client_manager.invalidate_client(account_id)
    return {"success": True, "message": "Client invalidated"}


# ==================== Bulk operations ====================


@router.post(
    "/bulk/status",
    response_model=BulkOperationResponse,
    status_code=status.HTTP_200_OK,
)
async def bulk_update_status(
    payload: BulkStatusUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """Массовое обновление статуса аккаунтов (владелец — текущий пользователь)."""
    affected = await service.bulk_update_status(
        account_ids=payload.account_ids,
        owner_id=current_user.id,
        new_status=payload.status,
        status_message=payload.status_message,
    )
    return BulkOperationResponse(
        affected=affected,
        message=f"Updated {affected} accounts to status={payload.status}",
    )


@router.post(
    "/bulk/delete",
    response_model=BulkOperationResponse,
    status_code=status.HTTP_200_OK,
)
async def bulk_delete(
    payload: BulkStatusUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    service: AccountService = Depends(get_service),
):
    """Массовое удаление (мягкое: is_active=False) аккаунтов."""
    affected = await service.bulk_delete(
        account_ids=payload.account_ids, owner_id=current_user.id
    )
    return BulkOperationResponse(
        affected=affected,
        message=f"Deactivated {affected} accounts",
    )
