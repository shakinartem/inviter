"""
Модели модуля parser — парсер чатов и пользователей по нише.

Содержит:
- ParsedChat       — спарсенный Telegram-чат/группа/супергруппа
- ParsedUser       — пользователь чата (участник)

Поддерживаемые источники (source):
- tgstat           — парсинг через TGStat API/HTML
- telemetr         — парсинг через Telemetr
- telegram_search  — глобальный поиск Telegram (SearchGlobal)
- telegram_dialogs — собственные диалоги аккаунта
- manual           — ручное добавление
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.features.auth.models import User
    from app.features.campaigns.models import Campaign


PARSER_SOURCES: tuple[str, ...] = (
    "tgstat",
    "telemetr",
    "telegram_search",
    "telegram_dialogs",
    "manual",
)
"""Допустимые источники парсинга."""


class ParsedChat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Спарсенный Telegram-чат/группа/супергруппа.

    Хранит полную информацию о чате, полученную из различных источников
    (TGStat, Telemetr, глобальный поиск Telegram).
    """

    __tablename__ = "parsed_chats"

    # ==================== Ownership ====================
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID владельца (User), инициировавшего парсинг",
    )

    campaign_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("campaigns.id"),
        nullable=True,
    )

    # ==================== Telegram identifiers ====================
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        doc="Telegram ID чата (глобальный уникальный идентификатор)",
    )
    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Telegram @username чата (без @)",
    )
    title: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        doc="Название чата",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Описание чата (about/info)",
    )
    access_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Access hash для доступа к чату через MTProto",
    )

    # ======================= Type =======================
    chat_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        doc="Тип: group, supergroup, channel, chat",
    )

    # ==================== Participants ====================
    participants_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Общее количество участников (по данным источника)",
    )
    active_participants: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Примерное количество активных участников (online за последние дни)",
    )

    # ==================== Classification ====================
    category: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
        doc="Категория чата (например, 'crypto', 'business', 'tech')",
    )
    niche: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
        doc="Ниша (более узкая, чем category; например, 'defi', 'nft')",
    )
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(64)),
        nullable=True,
        doc="Теги/ключевые слова для поиска и фильтрации",
    )

    # ==================== Localization ====================
    language: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        index=True,
        doc="Основной язык чата (ISO 639-1, например 'ru', 'en')",
    )
    country: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Страна чата (ISO 3166-1 alpha-2, например 'RU', 'US')",
    )

    # ==================== Status ====================
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Является ли чат публичным (имеет @username или найден через поиск)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Активен ли чат (не удалён, не заблокирован)",
    )
    is_restricted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Есть ли ограничения (возрастные, страновые)",
    )

    # ==================== Source & Parsing ====================
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        doc=(
            f"Источник данных. Один из {PARSER_SOURCES}. "
            "Определяет, откуда была получена информация."
        ),
    )
    last_parsed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Когда в последний раз парсился этот чат",
    )
    parse_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        doc="Сколько раз этот чат был спарсен",
    )

    # ==================== Engagement ====================
    avg_posts_per_day: Mapped[float | None] = mapped_column(
        nullable=True,
        doc="Среднее количество постов в день (для каналов)",
    )
    avg_reach_per_post: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Средний охват на пост (для каналов, ERR)",
    )
    engagement_rate: Mapped[float | None] = mapped_column(
        nullable=True,
        doc="Уровень вовлечённости (0.0 .. 1.0)",
    )

    # ==================== Metadata ====================
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        doc=(
            "Произвольные метаданные в JSONB. "
            "Может содержать: ссылки, скриншоты, цену рекламы, "
            "владельца чата, контакты и т.п."
        ),
    )

    # ==================== Relationships ====================
    owner: Mapped["User"] = relationship(
        back_populates="parsed_chats",
        lazy="selectin",
        doc="Владелец (пользователь, инициировавший парсинг)",
    )
    campaign: Mapped["Campaign | None"] = relationship(
        back_populates="parsed_chats",
        lazy="select",
        doc="Кампания, использующая этот чат как источник (если привязан)",
    )

    # ==================== Computed helpers ====================
    @property
    def display_name(self) -> str:
        """Лучшее отображение: title / @username / chat_id."""
        return self.title or f"@{self.username}" or str(self.chat_id)

    @property
    def is_channel(self) -> bool:
        """Является ли чат каналом."""
        return self.chat_type == "channel"

    @property
    def is_group(self) -> bool:
        """Является ли чат группой/супергруппой."""
        return self.chat_type in ("group", "supergroup")

    def __repr__(self) -> str:
        return (
            f"<ParsedChat id={self.id} title={self.title!r} "
            f"chat_id={self.chat_id} source={self.source!r} "
            f"members={self.participants_count}>"
        )

    def __str__(self) -> str:
        return f"ParsedChat({self.display_name}, source={self.source})"


class ParsedUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Спарсенный пользователь (участник чата).

    Хранит информацию о пользователе, полученную при парсинге чата.
    """

    __tablename__ = "parsed_users"

    # ==================== Ownership ====================
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID владельца (User)",
    )
    chat_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("parsed_chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID чата (ParsedChat), в котором найден пользователь",
    )

    # ==================== Telegram identifiers ====================
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        doc="Telegram user_id пользователя",
    )
    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Telegram @username (без @)",
    )
    first_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        doc="Имя пользователя",
    )
    last_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        doc="Фамилия пользователя",
    )
    phone: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        doc="Номер телефона (если доступен, редко)",
    )

    # ==================== Status ====================
    status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        doc="Статус: member, admin, creator, restricted, banned, left",
    )
    is_bot: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Является ли ботом",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Верифицирован ли пользователь Telegram",
    )
    is_scam: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Помечен ли как scam",
    )
    is_fake: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Помечен ли как fake",
    )

    # ==================== Activity ====================
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Когда пользователь был последний раз онлайн",
    )
    was_online_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Дата последнего появления в этом чате",
    )
    msg_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Количество сообщений пользователя в чате (если доступно)",
    )

    # ==================== Relationships ====================
    chat: Mapped["ParsedChat"] = relationship(
        lazy="selectin",
        doc="Чат, в котором найден пользователь",
    )

    # ==================== Helpers ====================
    @property
    def display_name(self) -> str:
        """Лучшее отображение пользователя."""
        return self.first_name or self.username or str(self.user_id)

    def __repr__(self) -> str:
        return (
            f"<ParsedUser id={self.id} user_id={self.user_id} "
            f"username={self.username!r} status={self.status!r}>"
        )

    def __str__(self) -> str:
        return f"ParsedUser({self.display_name}, status={self.status})"
