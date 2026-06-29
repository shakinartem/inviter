"""
Модель Proxy — прокси-сервер для подключения Telegram-аккаунтов.

Поддерживаемые типы прокси:
- HTTP
- SOCKS5
- MTProto (Telegram-specific)

Поля модели совместимы с ``TelegramClientManager._build_proxy()``.

NOTE: We intentionally do NOT import `User` at module level here.
`relationship("User")` is resolved lazily via Base.registry after all
models are imported. This avoids cycles like:
  proxies.models -> auth.models -> parser.models -> ... -> proxies.models
"""

from __future__ import annotations

import ipaddress
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.features.accounts.models import Account
    from app.features.auth.models import User


PROXY_TYPES: tuple[str, ...] = ("http", "socks5", "mtproto")
"""Допустимые типы прокси."""


class Proxy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Прокси-сервер для маршрутизации Telegram-трафика."""

    __tablename__ = "proxies"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID владельца прокси (User)",
    )

    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        doc="Человекочитаемое имя прокси (например, 'DC1 Proxy 1')",
    )
    scheme: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="socks5",
        doc="Тип прокси. Один из: http, socks5, mtproto.",
    )

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
        doc="Имя пользователя для аутентификации (если требуется)",
    )
    password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Пароль для аутентификации (если требуется)",
    )
    secret: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Секрет для MTProto-прокси",
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Страна расположения прокси-сервера",
    )
    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Город расположения прокси-сервера",
    )

    ping_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Время отклика в миллисекундах",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Когда в последний раз проверялась работоспособность",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Активен ли прокси (ручной флаг)",
    )
    is_working: Mapped[bool | None] = mapped_column(
        Boolean,
        default=None,
        nullable=True,
        index=True,
        doc="Работоспособен ли прокси (None — не проверялся)",
    )
    status_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Пояснение к статусу",
    )

    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        doc="Произвольные метаданные",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Произвольные заметки владельца",
    )

    # ==================== Relationships ====================
    # "User" is resolved lazily by SA from Base.registry.
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="proxies",
        lazy="selectin",
        doc="Владелец прокси",
    )
    accounts: Mapped[list["Account"]] = relationship(
        back_populates="proxy",
        lazy="select",
        doc="Аккаунты, использующие этот прокси",
    )

    @property
    def proxy_type(self) -> str:
        return self.scheme

    @property
    def display_name(self) -> str:
        return self.title or f"{self.host}:{self.port}"

    @property
    def in_use_count(self) -> int:
        return len(self.accounts) if self.accounts else 0

    @property
    def active_accounts_count(self) -> int:
        if not self.accounts:
            return 0
        return sum(1 for a in self.accounts if a.is_active)

    def validate_connection_string(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    def to_proxy_dict(self) -> dict[str, Any] | None:
        scheme = self.scheme.lower()
        if scheme == "mtproto":
            return {
                "proxy_type": "mtproto",
                "dc_id": 1,
                "server": self.host,
                "port": self.port,
                "secret": self.secret or self.password or "",
            }
        result: dict[str, Any] = {
            "proxy_type": scheme,
            "addr": self.host,
            "port": self.port,
            "rdns": True,
        }
        if self.username:
            result["username"] = self.username
        if self.password:
            result["password"] = self.password
        return result

    def __repr__(self) -> str:
        return (
            f"<Proxy id={self.id} title={self.title!r} "
            f"scheme={self.scheme!r} host={self.host!r}:{self.port} "
            f"working={self.is_working}>"
        )

    def __str__(self) -> str:
        return f"Proxy({self.display_name}, scheme={self.scheme})"

    @staticmethod
    def is_valid_port(port: int) -> bool:
        return 1 <= port <= 65535

    @staticmethod
    def is_valid_host(host: str) -> bool:
        if not host:
            return False
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            pass
        if "." in host:
            return all(c.isalnum() or c in ".-_" for c in host)
        return False