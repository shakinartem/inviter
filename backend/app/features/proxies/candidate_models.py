"""
Модель ProxyCandidate — кандидат прокси, полученный из импорта.

Используется как промежуточное хранилище при импорте прокси
из текстовых ссылок или других источников. После проверки и одобрения
становится рабочим Proxy в таблице proxies.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.features.auth.models import User


CANDIDATE_STATUS_TYPES: tuple[str, ...] = (
    "new", "checking", "alive", "dead", "approved", "rejected",
)
"""Допустимые статусы кандидата."""

CANDIDATE_SOURCE_TYPES: tuple[str, ...] = (
    "manual_text", "mtproto_text", "telegram_channel", "url_list", "local_adapter",
)
"""Допустимые типы источника кандидата."""

CANDIDATE_PROXY_TYPES: tuple[str, ...] = (
    "socks5", "http", "mtproto", "local_adapter", "unknown",
)
"""Допустимые типы прокси для кандидата."""


class ProxyCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Кандидат прокси-сервера, полученный из импорта.

    После проверки и одобрения конвертируется в рабочий Proxy.
    """

    __tablename__ = "proxy_candidates"

    # ==================== Identity ====================
    proxy_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
        doc="Тип прокси (socks5, http, mtproto, local_adapter, unknown)",
    )

    # ==================== Connection parameters ====================
    host: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="IP-адрес или доменное имя прокси-сервера",
    )
    port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Порт прокси-сервера (1–65535)",
    )
    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Имя пользователя для аутентификации на прокси",
    )
    password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Пароль для аутентификации на прокси (маскируется в API)",
    )
    secret: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Секрет для MTProto-прокси",
    )

    # ==================== Source info ====================
    raw_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Исходная ссылка/текст, из которого получен кандидат",
    )
    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="manual_text",
        doc="Тип источника: manual_text, mtproto_text, telegram_channel, url_list, local_adapter",
    )
    source_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Название источника (например, username канала)",
    )

    # ==================== Status ====================
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="new",
        index=True,
        doc="Статус кандидата: new, checking, alive, dead, approved, rejected",
    )
    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Оценка качества (субъективная, 0–100)",
    )

    # ==================== Health ====================
    latency_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Время отклика в миллисекундах (результат последней проверки)",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Когда в последний раз проверялась работоспособность",
    )
    last_error: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Текст последней ошибки проверки",
    )

    # ==================== Ownership ====================
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID владельца (User)",
    )

    owner: Mapped["User"] = relationship(
        lazy="selectin",
        doc="Владелец кандидата",
    )

    # ==================== Display ====================
    @property
    def display_name(self) -> str:
        """Лучшее отображение для UI: host:port."""
        return f"{self.host}:{self.port}"

    def __repr__(self) -> str:
        return (
            f"<ProxyCandidate id={self.id} host={self.host!r}:{self.port} "
            f"type={self.proxy_type!r} status={self.status!r}>"
        )

    def __str__(self) -> str:
        return f"ProxyCandidate({self.display_name}, type={self.proxy_type}, status={self.status})"

    # ==================== Validation ====================
    @staticmethod
    def is_valid_port(port: int) -> bool:
        """Проверка валидности порта."""
        return 1 <= port <= 65535