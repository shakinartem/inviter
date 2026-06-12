"""
Pydantic-схемы модуля proxies.

Содержит:
- ProxyCreate          — создание одного прокси
- ProxyUpdate          — частичное обновление
- ProxyResponse        — полный ответ (с данными о подключённых аккаунтах)
- ProxyListItem        — краткая схема для списков
- ProxyListResponse    — список с пагинацией
- ProxyListFilter      — фильтры
- ProxyTestResult      — результат проверки прокси
- BulkProxyCreate      — массовое создание (список)
- ProxyBulkCreateResult — результат массового создания
- ProxyStats           — сводная статистика
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.accounts.schemas import AccountListItem
from app.features.proxies.models import PROXY_TYPES

# ==================== Type aliases ====================

ProxyScheme = Literal["http", "socks5", "mtproto"]
"""Допустимые типы прокси-схем."""


# ==================== Create / Update ====================


class ProxyCreate(BaseModel):
    """Схема для создания нового прокси-сервера."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "title": "My SOCKS5 Proxy",
                "scheme": "socks5",
                "host": "123.123.123.123",
                "port": 1080,
                "username": "user",
                "password": "pass",
                "secret": None,
                "country": "RU",
                "city": "Moscow",
                "notes": "For Telegram accounts",
                "extra_data": {"provider": "bestproxy", "price": 1.5},
            }
        },
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Человекочитаемое имя прокси",
    )
    scheme: ProxyScheme = Field(
        default="socks5",
        description="Тип прокси: http, socks5 или mtproto",
    )

    # Connection
    host: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="IP-адрес или доменное имя прокси-сервера",
    )
    port: int = Field(
        ...,
        ge=1,
        le=65535,
        description="Порт прокси-сервера",
    )
    username: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Имя пользователя для аутентификации",
    )
    password: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Пароль для аутентификации",
    )
    secret: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Секрет для MTProto-прокси",
    )

    # Geo
    country: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Страна расположения прокси",
    )
    city: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Город расположения прокси",
    )

    # Metadata
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Произвольные заметки",
    )
    extra_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Произвольные метаданные (провайдер, регион и т.п.)",
    )

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Простая валидация хоста."""
        if not v.strip():
            raise ValueError("Хост не может быть пустым")
        return v.strip()

    @field_validator("scheme")
    @classmethod
    def validate_scheme(cls, v: str) -> str:
        """Проверка схемы прокси."""
        v = v.lower()
        if v not in PROXY_TYPES:
            raise ValueError(
                f"Недопустимый тип прокси '{v}'. Допустимые: {PROXY_TYPES}"
            )
        return v


class ProxyUpdate(BaseModel):
    """Частичное обновление прокси (PATCH)."""
    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    scheme: Optional[ProxyScheme] = None
    host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, max_length=255)
    secret: Optional[str] = Field(default=None, max_length=255)
    country: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    extra_data: Optional[dict[str, Any]] = None

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Хост не может быть пустым")
        return v.strip() if v else v

    @field_validator("scheme")
    @classmethod
    def validate_scheme(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.lower()
            if v not in PROXY_TYPES:
                raise ValueError(
                    f"Недопустимый тип прокси '{v}'. Допустимые: {PROXY_TYPES}"
                )
        return v


# ==================== Response schemas ====================


class ProxyResponse(BaseModel):
    """
    Полная информация о прокси.
    Используется в GET /proxies/{id}, POST /proxies.
    """
    model_config = ConfigDict(from_attributes=True)

    # Identity
    id: UUID
    owner_id: UUID
    title: str
    scheme: str

    # Connection
    host: str
    port: int
    username: Optional[str]
    password: Optional[str]
    secret: Optional[str]

    # Geo
    country: Optional[str]
    city: Optional[str]

    # Health
    ping_ms: Optional[float]
    last_checked_at: Optional[datetime]

    # Status
    is_active: bool
    is_working: Optional[bool]
    status_message: Optional[str]

    # Metadata
    extra_data: Optional[dict[str, Any]]
    notes: Optional[str]

    # Usage
    in_use_count: int = Field(
        default=0,
        ge=0,
        description="Сколько аккаунтов используют этот прокси",
    )
    active_accounts_count: int = Field(
        default=0,
        ge=0,
        description="Сколько активных аккаунтов на этом прокси",
    )

    # Audit
    created_at: datetime
    updated_at: datetime


class ProxyListItem(BaseModel):
    """Краткая схема для списка прокси."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    scheme: str
    host: str
    port: int
    country: Optional[str]
    is_active: bool
    is_working: Optional[bool]
    ping_ms: Optional[float]
    last_checked_at: Optional[datetime]
    in_use_count: int = Field(default=0, ge=0)
    created_at: datetime


class ProxyListResponse(BaseModel):
    """Ответ со списком прокси + пагинацией."""
    model_config = ConfigDict(from_attributes=True)

    items: list[ProxyListItem] = Field(
        ...,
        description="Прокси на текущей странице",
    )
    total: int = Field(..., ge=0, description="Всего прокси у владельца")
    skip: int = Field(..., ge=0, description="Смещение")
    limit: int = Field(..., ge=1, description="Размер страницы")


class ProxyWithAccounts(BaseModel):
    """Прокси со списком привязанных аккаунтов (для детального просмотра)."""
    model_config = ConfigDict(from_attributes=True)

    proxy: ProxyResponse
    accounts: list[AccountListItem] = Field(
        default_factory=list,
        description="Аккаунты, использующие этот прокси",
    )


# ==================== Filters ====================


class ProxyListFilter(BaseModel):
    """
    Фильтры для получения списка прокси.

    Поддерживает: схему, активность, работоспособность,
    поиск по title/host, страну, диапазон времени создания.
    """
    model_config = ConfigDict(from_attributes=True)

    scheme: Optional[ProxyScheme] = None
    is_active: Optional[bool] = None
    is_working: Optional[bool] = None
    country: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Фильтр по стране",
    )
    search: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Поиск по title/host (ILIKE)",
    )
    created_after: Optional[datetime] = Field(
        default=None,
        description="Только прокси, созданные после этой даты",
    )
    created_before: Optional[datetime] = Field(
        default=None,
        description="Только прокси, созданные до этой даты",
    )


# ==================== Test ====================


class ProxyTestResult(BaseModel):
    """Результат проверки работоспособности прокси."""
    model_config = ConfigDict(from_attributes=True)

    proxy_id: Optional[UUID] = Field(
        default=None,
        description="ID прокси (если тестируется существующий)",
    )
    host: str
    port: int
    scheme: str
    is_working: bool = Field(
        ...,
        description="Работоспособен ли прокси",
    )
    ping_ms: Optional[float] = Field(
        default=None,
        ge=0,
        description="Время отклика в миллисекундах",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Описание ошибки, если прокси не работает",
    )
    tested_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Когда была выполнена проверка (UTC)",
    )


class BulkTestRequest(BaseModel):
    """Запрос на массовое тестирование прокси."""
    model_config = ConfigDict(from_attributes=True)

    proxy_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Список ID прокси для проверки",
    )


class BulkTestResult(BaseModel):
    """Результат массового тестирования."""
    model_config = ConfigDict(from_attributes=True)

    results: list[ProxyTestResult]
    total: int
    success_count: int
    fail_count: int


# ==================== Bulk create ====================


class BulkProxyCreate(BaseModel):
    """Запрос на массовое создание прокси (из списка или текста)."""
    model_config = ConfigDict(from_attributes=True)

    proxies: list[ProxyCreate] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Список прокси для создания",
    )


class ProxyBulkCreateResult(BaseModel):
    """Результат массового создания прокси."""
    model_config = ConfigDict(from_attributes=True)

    created: list[ProxyResponse]
    failed: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Список ошибок при создании (содержит index и error)",
    )
    total_requested: int
    success_count: int
    fail_count: int


class ProxyTextImport(BaseModel):
    """
    Импорт прокси из текстового формата (CSV/TSV/построчный).

    Формат строки: scheme://user:password@host:port
    или scheme://host:port (один на строку).
    """
    model_config = ConfigDict(from_attributes=True)

    text: str = Field(
        ...,
        min_length=1,
        description=(
            "Текст с прокси (построчно). "
            "Формат: scheme://user:password@host:port или scheme://host:port"
        ),
    )
    default_scheme: ProxyScheme = Field(
        default="socks5",
        description="Тип прокси по умолчанию (если не указан в строке)",
    )


# ==================== Stats ====================


class ProxyStats(BaseModel):
    """Сводная статистика по прокси владельца."""
    model_config = ConfigDict(from_attributes=True)

    total: int = Field(..., ge=0)
    active: int = Field(..., ge=0)
    working: int = Field(..., ge=0, description="Подтверждённо рабочие")
    failing: int = Field(..., ge=0, description="Подтверждённо нерабочие")
    unchecked: int = Field(..., ge=0, description="Ещё не проверенные")
    http_count: int = Field(..., ge=0)
    socks5_count: int = Field(..., ge=0)
    mtproto_count: int = Field(..., ge=0)
    avg_ping_ms: Optional[float] = Field(
        default=None,
        ge=0,
        description="Средний пинг по рабочим прокси",
    )
    in_use_total: int = Field(
        ...,
        ge=0,
        description="Всего привязанных аккаунтов к прокси",
    )