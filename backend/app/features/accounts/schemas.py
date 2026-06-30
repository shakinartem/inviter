"""
Pydantic-схемы модуля accounts.

Содержит:
- AccountCreate       — для создания аккаунта
- AccountUploadSession — для загрузки .session-файла
- AccountUpdate       — частичное обновление
- AccountResponse     — полный ответ с proxy и статистикой
- AccountListResponse — укороченная схема для списков
- AccountListFilter   — фильтры
- AccountStatusUpdate — ручное изменение статуса
- AccountCheckResponse — результат /check
- AccountStats        — сводная статистика
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.accounts.models import ACCOUNT_STATUSES


# ==================== Type aliases ====================

AccountStatus = Literal[
    "active", "idle", "limited", "cooldown", "banned", "inactive", "error"
]
"""
Допустимые статусы аккаунта.
Совпадают с app.features.accounts.models.ACCOUNT_STATUSES.
"""


# ==================== Create / Update ====================


class AccountCreate(BaseModel):
    """
    Схема для регистрации нового Telegram-аккаунта.

    Содержит технические данные, необходимые для будущего подключения.
    Сам .session-файл загружается отдельным эндпоинтом (POST /upload-session).
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "label": "Main Account",
                "phone": "+79991234567",
                "api_id": 123456,
                "api_hash": "0123456789abcdef0123456789abcdef",
                "proxy_id": None,
                "notes": "Personal account",
            }
        },
    )

    label: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Человекочитаемое имя аккаунта",
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Номер телефона в международном формате (+79991234567)",
    )
    api_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Telegram API ID (https://my.telegram.org)",
    )
    api_hash: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=255,
        description="Telegram API HASH (https://my.telegram.org)",
    )
    proxy_id: Optional[UUID] = Field(
        default=None,
        description="ID прокси, через который подключается аккаунт",
    )
    session_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description=(
            "Имя файла сессии (без расширения). "
            "Генерируется автоматически, если не задано"
        ),
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Произвольные заметки",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        validation_alias="extra_data",
        serialization_alias="metadata",
        description=(
            "Произвольные данные (device_model, system_version, "
            "app_version, lang_code и т.п.)"
        ),
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Очистить и проверить номер телефона."""
        if v is None:
            return v
        # Оставляем только цифры и +
        cleaned = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        if len(cleaned) < 7:
            raise ValueError("Некорректный номер телефона (слишком короткий)")
        if not cleaned.startswith("+"):
            # Мягко: принимаем и без '+' (Telethon справится)
            return "+" + cleaned
        return cleaned

    @field_validator("session_name")
    @classmethod
    def validate_session_name(cls, v: Optional[str]) -> Optional[str]:
        """Защита от path-traversal в имени .session-файла."""
        if v is None:
            return v
        if not v or not all(c.isalnum() or c in ("_", "-") for c in v):
            raise ValueError(
                "session_name может содержать только буквы, цифры, '_' и '-'"
            )
        return v


class AccountUpdate(BaseModel):
    """Частичное обновление аккаунта (PATCH)."""
    model_config = ConfigDict(from_attributes=True)

    label: Optional[str] = Field(default=None, min_length=1, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=32)
    proxy_id: Optional[UUID] = None
    api_id: Optional[int] = Field(default=None, ge=1)
    api_hash: Optional[str] = Field(default=None, min_length=10, max_length=255)
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        validation_alias="extra_data",
        serialization_alias="metadata",
    )


class AccountStatusUpdate(BaseModel):
    """Ручное изменение статуса аккаунта (PATCH /status)."""
    model_config = ConfigDict(from_attributes=True)

    status: AccountStatus = Field(..., description="Новый статус")
    status_message: Optional[str] = Field(default=None, max_length=500)
    cooldown_until: Optional[datetime] = None
    banned_until: Optional[datetime] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ACCOUNT_STATUSES:
            raise ValueError(
                f"Недопустимый статус '{v}'. Допустимые: {ACCOUNT_STATUSES}"
            )
        return v


# ==================== Session upload ====================


class AccountUploadSession(BaseModel):
    """
    Метаданные для загрузки .session-файла.

    Сам файл передаётся через multipart/form-data (поле `file`).
    Эта схема — для случая, когда фронт отправляет JSON-описание
    (например, file_id от внешнего хранилища) — зарезервирована на будущее.
    Для текущей реализации используется File upload напрямую.
    """
    model_config = ConfigDict(from_attributes=True)

    session_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Имя файла сессии (должно совпадать с Account.session_name)",
    )
    file_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Размер файла в байтах (для предварительной валидации)",
    )
    overwrite: bool = Field(
        default=True,
        description="Перезаписать ли существующий .session-файл",
    )


# ==================== Response schemas ====================


class ProxyShort(BaseModel):
    """Краткая информация о прокси (вложенная в AccountResponse)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    scheme: str
    host: str
    port: int
    is_active: bool


class AccountResponse(BaseModel):
    """
    Полная информация об аккаунте (включая proxy и метрики).
    Используется в GET /accounts/{id}, POST /accounts.
    """
    model_config = ConfigDict(from_attributes=True)

    # Identity
    id: UUID
    owner_id: UUID
    label: str
    phone: Optional[str]
    session_name: str
    api_id: Optional[int]
    api_hash: Optional[str]

    # Proxy
    proxy_id: Optional[UUID]
    proxy: Optional[ProxyShort] = Field(
        default=None,
        description="Вложенная информация о прокси",
    )

    # Telegram profile
    telegram_user_id: Optional[int]
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    is_premium: bool
    is_bot: bool

    # Status
    status: AccountStatus
    status_message: Optional[str]
    is_active: bool

    # Timestamps
    last_seen_at: Optional[datetime]
    last_used_at: Optional[datetime]
    last_checked_at: Optional[datetime]

    # Cooldown / Banned
    cooldown_until: Optional[datetime]
    banned_until: Optional[datetime]

    # Metrics
    daily_invite_count: int
    daily_invite_reset_at: Optional[datetime]
    total_invites: int
    total_invite_errors: int
    total_floodwaits: int
    success_rate: float

    # Metadata
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        validation_alias="account_metadata",
        description="Произвольные данные (алиас для extra_data)",
    )
    notes: Optional[str]

    # Audit
    created_at: datetime
    updated_at: datetime

    # Computed
    fingerprint: Optional[str] = Field(
        default=None,
        description="Короткий отпечаток аккаунта (для логов)",
    )


class AccountListItem(BaseModel):
    """Укороченная схема для списков (используется в AccountListResponse)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    phone: Optional[str]
    username: Optional[str]
    status: AccountStatus
    is_active: bool
    is_premium: bool
    proxy_id: Optional[UUID]
    last_used_at: Optional[datetime]
    last_checked_at: Optional[datetime]
    daily_invite_count: int
    total_invites: int
    success_rate: float
    created_at: datetime


class AccountListResponse(BaseModel):
    """
    Ответ со списком аккаунтов + пагинацией.
    """
    model_config = ConfigDict(from_attributes=True)

    items: list[AccountListItem] = Field(
        ...,
        description="Аккаунты на текущей странице",
    )
    total: int = Field(..., ge=0, description="Всего аккаунтов у владельца")
    skip: int = Field(..., ge=0, description="Смещение")
    limit: int = Field(..., ge=1, description="Размер страницы")


# ==================== Filters ====================


class AccountListFilter(BaseModel):
    """
    Фильтры для получения списка аккаунтов.

    Поддерживает: статус, активность, прокси, премиум,
    поиск по label/phone/username, диапазон дат создания.
    """
    model_config = ConfigDict(from_attributes=True)

    status: Optional[AccountStatus] = None
    is_active: Optional[bool] = None
    proxy_id: Optional[UUID] = None
    is_premium: Optional[bool] = None
    search: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Поиск по label/phone/username (ILIKE)",
    )
    created_after: Optional[datetime] = Field(
        default=None,
        description="Только аккаунты, созданные после этой даты",
    )
    created_before: Optional[datetime] = Field(
        default=None,
        description="Только аккаунты, созданные до этой даты",
    )


# ==================== Check / Session upload results ====================


class SessionUploadResult(BaseModel):
    """Результат загрузки .session-файла."""
    model_config = ConfigDict(from_attributes=True)

    account_id: UUID
    session_name: str
    session_size: int = Field(..., ge=0, description="Размер файла в байтах")
    validated: bool = Field(
        ...,
        description="Прошла ли базовая валидация (SQLite-сигнатура)",
    )
    message: str
    telegram_user_id: Optional[int] = None
    phone: Optional[str] = None


class AccountCheckResponse(BaseModel):
    """
    Результат проверки аккаунта (POST /accounts/{id}/check).

    Возвращает:
    - is_authorized — авторизован ли .session
    - данные профиля (если авторизован)
    - новый статус + сообщение (если есть ошибка)
    - error_code / error_message для машинной обработки
    """
    model_config = ConfigDict(from_attributes=True)

    account_id: UUID
    is_authorized: bool
    telegram_user_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_premium: bool = False
    is_bot: bool = False
    status: AccountStatus
    status_message: Optional[str] = None
    error_code: Optional[str] = Field(
        default=None,
        description="Машиночитаемый код ошибки (FLOOD_WAIT, AUTH_KEY_UNREGISTERED и т.д.)",
    )
    error_message: Optional[str] = None
    checked_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Когда была выполнена проверка (UTC)",
    )


class AuthStartResponse(BaseModel):
    """Результат начала авторизации."""
    model_config = ConfigDict(from_attributes=True)

    account_id: UUID
    status: str = "code_sent"
    phone_code_hash: str = Field(..., description="Хеш кода для подтверждения")
    timeout: int = Field(default=30, description="Таймаут для ввода кода (сек)")


class AuthConfirmRequest(BaseModel):
    """Запрос на подтверждение кода авторизации."""
    code: str = Field(..., min_length=1, max_length=10, description="Код из SMS/Telegram")
    password: Optional[str] = Field(default=None, description="Пароль 2FA (если требуется)")


class AuthConfirmResponse(BaseModel):
    """Результат подтверждения авторизации."""
    model_config = ConfigDict(from_attributes=True)

    account_id: UUID
    authorized: bool
    telegram_user_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_premium: bool = False
    is_bot: bool = False
    phone: Optional[str] = None
    status: str = "active"
    status_message: Optional[str] = None


# ==================== Stats ====================


class AccountStats(BaseModel):
    """Сводная статистика по аккаунтам владельца."""
    model_config = ConfigDict(from_attributes=True)

    total: int
    active: int
    banned: int
    limited: int
    cooldown: int
    inactive: int
    in_cooldown_now: int = Field(
        ...,
        description="Сколько аккаунтов сейчас на cooldown (cooldown_until > now)",
    )
    premium_count: int
    total_invites_today: int
    avg_success_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Средний success_rate по всем аккаунтам",
    )


# ==================== Health / Pool ====================


class ClientPoolHealth(BaseModel):
    """Health-check пула Telegram-клиентов."""
    model_config = ConfigDict(from_attributes=True)

    total_cached: int = Field(..., ge=0)
    connected: int = Field(..., ge=0)
    disconnected: int = Field(..., ge=0)
    sessions_dir: str
    redis_enabled: bool

