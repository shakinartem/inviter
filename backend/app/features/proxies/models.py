"""
Модель Proxy — прокси-сервер для подключения Telegram-аккаунтов.

Поддерживаемые типы прокси:
- HTTP
- SOCKS5
- MTProto (Telegram-specific)

Поля модели совместимы с ``TelegramClientManager._build_proxy()``.
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
    """Прокси-сервер для маршрутизации Telegram-трафика.

    Хранит параметры подключения, результаты последней проверки
    и привязку к владельцу (User) и аккаунтам (Account).
    """

    __tablename__ = "proxies"

    # ==================== Ownership ====================
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID владельца прокси (User)",
    )

    # ==================== Main identifiers ====================
    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        doc="Человекочитаемое имя прокси (например, 'DC1 Proxy 1')",
    )
    scheme: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="socks5",
        doc=(
            "Тип прокси. Один из: http, socks5, mtproto. "
            "Используется в _build_proxy() для Telethon."
        ),
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
        doc="Имя пользователя для аутентификации на прокси (если требуется)",
    )
    password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Пароль для аутентификации на прокси (если требуется)",
    )
    secret: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Секрет для MTProto-прокси (используется как password в _build_proxy)",  # noqa: E501
    )

    # ==================== Geo information ====================
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

    # ==================== Ping / Health ====================
    ping_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Время отклика в миллисекундах (результат последней проверки)",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Когда в последний раз проверялась работоспособность",
    )

    # ==================== Status ====================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Активен ли прокси (ручной флаг). Неактивные не используются.",
    )
    is_working: Mapped[bool | None] = mapped_column(
        Boolean,
        default=None,
        nullable=True,
        index=True,
        doc="Работоспособен ли прокси (результат автоматической проверки). "
        "None — ещё не проверялся, True — рабочий, False — не работает.",
    )
    status_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Человекочитаемое пояснение к статусу (например, 'Connection refused')",
    )

    # ==================== Metadata ====================
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        doc="Произвольные метаданные (провайдер, регион, цена и т.п.)",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Произвольные заметки владельца",
    )

    # ==================== Relationships ====================
    owner: Mapped["User"] = relationship(
        back_populates="proxies",
        lazy="selectin",
        doc="Владелец прокси",
    )
    accounts: Mapped[list["Account"]] = relationship(
        back_populates="proxy",
        lazy="select",
        doc="Аккаунты, использующие этот прокси",
    )

    # ==================== Computed helpers ====================
    @property
    def proxy_type(self) -> str:
        """Алиас для ``scheme`` (для совместимости с внешним API)."""
        return self.scheme

    @property
    def display_name(self) -> str:
        """Лучшее отображение для UI: title / host:port / scheme."""
        return self.title or f"{self.host}:{self.port}"

    @property
    def in_use_count(self) -> int:
        """Количество аккаунтов, использующих этот прокси (через relationship)."""
        return len(self.accounts) if self.accounts else 0

    @property
    def active_accounts_count(self) -> int:
        """Количество активных аккаунтов на этом прокси."""
        if not self.accounts:
            return 0
        return sum(1 for a in self.accounts if a.is_active)

    # ==================== Validation helpers ====================
    def validate_connection_string(self) -> str:
        """Собрать строку подключения (без секретов) для логов."""
        return f"{self.scheme}://{self.host}:{self.port}"

    def to_proxy_dict(self) -> dict[str, Any] | None:
        """Преобразовать в dict-параметры для Telethon (как _build_proxy).

        Совместимо с ``TelegramClientManager._build_proxy()``.
        """
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

    # ==================== Display ====================
    def __repr__(self) -> str:
        return (
            f"<Proxy id={self.id} title={self.title!r} "
            f"scheme={self.scheme!r} host={self.host!r}:{self.port} "
            f"working={self.is_working}>"
        )

    def __str__(self) -> str:
        return f"Proxy({self.display_name}, scheme={self.scheme})"

    # ==================== Class utils ====================
    @staticmethod
    def is_valid_port(port: int) -> bool:
        """Проверка валидности порта."""
        return 1 <= port <= 65535

    @staticmethod
    def is_valid_host(host: str) -> bool:
        """Проверка, что хост выглядит как IP или домен."""
        if not host:
            return False
        # Пробуем распарсить как IP
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            pass
        # Базовая проверка домена
        if "." in host:
            return all(c.isalnum() or c in ".-_" for c in host)
        return False