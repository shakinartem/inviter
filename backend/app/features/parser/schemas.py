"""
Pydantic-схемы модуля parser — парсер чатов и пользователей по нише.

Содержит:
- ParsedChatCreate       — создание/ручное добавление чата
- ParsedChatUpdate       — частичное обновление
- ParsedChatResponse     — полный ответ
- ParsedChatListItem     — краткая схема для списка
- ParsedChatListResponse — список с пагинацией
- ParsedUserResponse     — ответ с пользователем
- ParsedUserListResponse — список пользователей
- ParserSearchRequest    — основной запрос парсинга
- ParserStats            — сводная статистика
- BulkParseRequest       — массовый парсинг
- ParserHistoryItem      — элемент истории парсингов
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==================== Type aliases ====================

ParserSource = Literal["tgstat", "telegram", "telemetr"]
"""Допустимые источники для запроса парсинга."""


# ==================== Create / Update ====================


class ParsedChatCreate(BaseModel):
    """Схема для ручного добавления или создания спарсенного чата."""
    model_config = ConfigDict(from_attributes=True)

    chat_id: int = Field(
        ...,
        description="Telegram ID чата",
    )
    username: Optional[str] = Field(
        default=None,
        max_length=255,
        description="@username чата (без @)",
    )
    title: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Название чата",
    )
    description: Optional[str] = Field(
        default=None,
        description="Описание чата",
    )
    access_hash: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Access hash для доступа через MTProto",
    )
    chat_type: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Тип: group, supergroup, channel, chat",
    )

    # Participants
    participants_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Общее количество участников",
    )
    active_participants: Optional[int] = Field(
        default=None,
        ge=0,
        description="Примерное количество активных участников",
    )

    # Classification
    category: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Категория (например, 'crypto', 'business')",
    )
    niche: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Ниша (например, 'defi', 'nft')",
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="Теги/ключевые слова",
    )

    # Localization
    language: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Язык (ISO 639-1, например 'ru', 'en')",
    )
    country: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Страна (ISO 3166-1 alpha-2)",
    )

    # Status
    is_public: bool = Field(default=True)
    is_active: bool = Field(default=True)
    is_restricted: bool = Field(default=False)

    # Source
    source: str = Field(
        default="manual",
        max_length=32,
        description="Источник данных",
    )

    # Engagement
    avg_posts_per_day: Optional[float] = Field(default=None, ge=0)
    avg_reach_per_post: Optional[int] = Field(default=None, ge=0)
    engagement_rate: Optional[float] = Field(default=None, ge=0, le=1)

    # Metadata
    extra_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Произвольные метаданные",
    )


class ParsedChatUpdate(BaseModel):
    """Частичное обновление спарсенного чата (PATCH)."""
    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = Field(default=None, max_length=512)
    username: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    chat_type: Optional[str] = Field(default=None, max_length=32)
    participants_count: Optional[int] = Field(default=None, ge=0)
    active_participants: Optional[int] = Field(default=None, ge=0)
    category: Optional[str] = Field(default=None, max_length=120)
    niche: Optional[str] = Field(default=None, max_length=120)
    tags: Optional[list[str]] = None
    language: Optional[str] = Field(default=None, max_length=10)
    country: Optional[str] = Field(default=None, max_length=10)
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None
    is_restricted: Optional[bool] = None
    avg_posts_per_day: Optional[float] = Field(default=None, ge=0)
    avg_reach_per_post: Optional[int] = Field(default=None, ge=0)
    engagement_rate: Optional[float] = Field(default=None, ge=0, le=1)
    extra_data: Optional[dict[str, Any]] = None


# ==================== Response schemas ====================


class ParsedChatResponse(BaseModel):
    """Полная информация о спарсенном чате."""
    model_config = ConfigDict(from_attributes=True)

    # Identity
    id: UUID
    owner_id: UUID

    # Telegram
    chat_id: int
    username: Optional[str]
    title: Optional[str]
    description: Optional[str]
    access_hash: Optional[str]
    chat_type: Optional[str]

    # Participants
    participants_count: Optional[int]
    active_participants: Optional[int]

    # Classification
    category: Optional[str]
    niche: Optional[str]
    tags: Optional[list[str]]

    # Localization
    language: Optional[str]
    country: Optional[str]

    # Status
    is_public: bool
    is_active: bool
    is_restricted: bool

    # Source
    source: str
    last_parsed_at: Optional[datetime]
    parse_count: int

    # Engagement
    avg_posts_per_day: Optional[float]
    avg_reach_per_post: Optional[int]
    engagement_rate: Optional[float]

    # Metadata
    extra_data: Optional[dict[str, Any]]

    # Audit
    created_at: datetime
    updated_at: datetime


class ParsedChatListItem(BaseModel):
    """Краткая схема для списка чатов."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat_id: int
    title: Optional[str]
    username: Optional[str]
    chat_type: Optional[str]
    participants_count: Optional[int]
    category: Optional[str]
    niche: Optional[str]
    language: Optional[str]
    source: str
    is_active: bool
    is_public: bool
    last_parsed_at: Optional[datetime]
    created_at: datetime


class ParsedChatListResponse(BaseModel):
    """Ответ со списком спарсенных чатов + пагинация."""
    model_config = ConfigDict(from_attributes=True)

    items: list[ParsedChatListItem]
    total: int = Field(..., ge=0)
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)


class ParsedUserResponse(BaseModel):
    """Информация о спарсенном пользователе."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    chat_id: UUID

    # Telegram
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]

    # Status
    status: Optional[str]
    is_bot: bool
    is_verified: bool
    is_scam: bool
    is_fake: bool

    # Activity
    last_seen: Optional[datetime]
    was_online_at: Optional[datetime]
    msg_count: Optional[int]

    # Audit
    created_at: datetime
    updated_at: datetime


class ParsedUserListResponse(BaseModel):
    """Ответ со списком спарсенных пользователей + пагинация."""
    model_config = ConfigDict(from_attributes=True)

    items: list[ParsedUserResponse]
    total: int = Field(..., ge=0)
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)


class MockParsedUsersCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., min_length=1, max_length=512)
    count: int = Field(default=10, ge=1, le=1000)
    username_prefix: str = Field(default="mock_user", min_length=1, max_length=64)
    include_bots: bool = False
    include_scam: bool = False
    include_fake: bool = False


# ==================== Parser request schemas ====================


class ParserSearchRequest(BaseModel):
    """
    Основной запрос парсинга чатов по нише.

    Позволяет задать поисковый запрос, источник,
    фильтры по количеству участников, языку, стране.
    """
    model_config = ConfigDict(from_attributes=True)

    # Search
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Поисковый запрос (ниша, тема, ключевые слова)",
    )
    source: ParserSource = Field(
        default="telegram",
        description=(
            "Источник парсинга: "
            "'telegram' — глобальный поиск Telegram (SearchGlobal); "
            "'tgstat' — парсинг TGStat; "
            "'telemetr' — парсинг Telemetr"
        ),
    )

    # Filters
    min_participants: int = Field(
        default=0,
        ge=0,
        description="Минимальное количество участников",
    )
    max_participants: int = Field(
        default=0,
        ge=0,
        description="Максимальное количество участников (0 — без ограничения)",
    )
    language: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Фильтр по языку (ISO 639-1)",
    )
    country: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Фильтр по стране (ISO 3166-1 alpha-2)",
    )
    chat_type: Optional[Literal["group", "supergroup", "channel", "chat"]] = Field(
        default=None,
        description="Фильтр по типу чата",
    )
    is_public: Optional[bool] = Field(
        default=True,
        description="Только публичные чаты",
    )

    # Pagination
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Максимальное количество результатов",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Смещение для пагинации",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Поисковый запрос не может быть пустым")
        return v.strip()


class BulkParseRequest(BaseModel):
    """Массовый парсинг по нескольким запросам."""
    model_config = ConfigDict(from_attributes=True)

    requests: list[ParserSearchRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Список запросов для массового парсинга",
    )
    deduplicate: bool = Field(
        default=True,
        description="Удалять дубликаты чатов (по chat_id)",
    )


class ParserHistoryItem(BaseModel):
    """Элемент истории парсинга."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    query: str = Field(..., description="Поисковый запрос")
    source: str = Field(..., description="Источник парсинга")
    chats_found: int = Field(..., ge=0)
    chats_saved: int = Field(..., ge=0)
    status: str = Field(
        ...,
        description="Статус: completed, failed, in_progress",
    )
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    created_at: datetime


# ==================== Stats ====================


class ParserStats(BaseModel):
    """Сводная статистика по спарсенным чатам."""
    model_config = ConfigDict(from_attributes=True)

    total_chats: int = Field(..., ge=0)
    active_chats: int = Field(..., ge=0)
    total_users: int = Field(..., ge=0)
    by_source: dict[str, int] = Field(
        default_factory=dict,
        description="Распределение по источникам (tgstat, telegram_search, ...)",
    )
    by_category: dict[str, int] = Field(
        default_factory=dict,
        description="Распределение по категориям",
    )
    by_language: dict[str, int] = Field(
        default_factory=dict,
        description="Распределение по языкам",
    )
    total_parses: int = Field(..., ge=0, description="Всего выполненных парсингов")
    avg_participants: Optional[float] = Field(
        default=None,
        ge=0,
        description="Среднее количество участников",
    )
