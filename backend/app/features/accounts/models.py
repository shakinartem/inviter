from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.features.auth.models import User
    from app.features.inviter.models import InviteTask
    from app.features.proxies.models import Proxy


# ==================== AccountStatus constants ====================
# Допустимые статусы аккаунта. Храним как VARCHAR(32) в БД.
ACCOUNT_STATUSES: tuple[str, ...] = (
    "active",      # работает нормально
    "idle",        # создан, но ещё не использовался
    "limited",     # есть ограничения (Slow Mode, PeerFlood и т.п.)
    "cooldown",    # действует floodwait / временный cooldown
    "banned",      # забанен / сессия невалидна
    "inactive",    # выключен пользователем (is_active=False)
    "error",       # непредвиденная ошибка при последней операции
)


def generate_session_name(prefix: str = "acc") -> str:
    """
    Сгенерировать уникальное имя файла сессии.
    Используется при создании Account, если пользователь не указал своё.

    Формат: {prefix}_{16-символов-hex}.
    Коллизий практически не бывает (8 байт энтропии).
    """
    return f"{prefix}_{secrets.token_hex(8)}"


def fingerprint_account(phone: str | None, api_id: int | None, session_name: str) -> str:
    """
    Посчитать короткий «отпечаток» аккаунта для логов (без утечки чувствительных данных).
    SHA-1 от (phone|api_id|session_name) → 8 hex-символов.
    """
    raw = f"{phone or ''}|{api_id or ''}|{session_name}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:8]


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Telegram-аккаунт пользователя системы.

    Хранит:
    - Идентификаторы (phone, session_name, telegram user_id)
    - Статусы (active, banned, limited, cooldown, inactive, idle, error)
    - Метрики использования (daily_invite_count, total_invites, success_rate)
    - Cooldown/banned-тайминги
    - Произвольные метаданные (premium, device fingerprint и т.д.)
    - Связи с владельцем (User), прокси (Proxy) и задачами инвайтинга (InviteTask)
    """

    __tablename__ = "accounts"

    # ==================== Ownership / Routing ====================
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID владельца аккаунта (User)",
    )
    proxy_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("proxies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="ID прокси, через который подключается аккаунт (опционально)",
    )

    # ==================== Main identifiers ====================
    label: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        doc="Человекочитаемое имя аккаунта (например, 'Main Account')",
    )
    phone: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        unique=True,
        index=True,
        doc="Номер телефона в международном формате (+79991234567)",
    )
    session_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc=(
            "Имя .session-файла (без расширения). "
            "Используется в пути ./sessions/{session_name}.session"
        ),
    )
    api_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Telegram API ID (https://my.telegram.org)",
    )
    api_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Telegram API HASH (https://my.telegram.org)",
    )

    # ==================== Telegram profile (заполняется при /check) ====================
    telegram_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        unique=True,
        index=True,
        doc="Telegram user_id (назначается Telegram, уникален глобально)",
    )
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    username: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
        doc="Telegram @username (без @)",
    )
    is_premium: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Telegram Premium-подписка",
    )
    is_bot: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Является ли аккаунт ботом (только для чтения)",
    )

    # ==================== Status / Activity ====================
    status: Mapped[str] = mapped_column(
        String(32),
        default="idle",
        nullable=False,
        index=True,
        doc=(
            f"Текущий статус. Один из {ACCOUNT_STATUSES}. "
            "Меняется автоматически по результатам операций или вручную."
        ),
    )
    status_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Человекочитаемое пояснение к текущему статусу (например, 'FloodWait 60s')",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Активен ли аккаунт (ручной флаг). Неактивные не используются для инвайтов.",
    )

    # ==================== Timestamps ====================
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Когда последний раз видели аккаунт онлайн (Telegram online)",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Когда аккаунт последний раз использовался для инвайта",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Когда в последний раз выполнялся /check (get_me())",
    )

    # ==================== Cooldown / Banned windows ====================
    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="До какого момента аккаунт на паузе (FloodWait, ручной cooldown)",
    )
    banned_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="До какого момента аккаунт считается забаненным",
    )

    # ==================== Metrics ====================
    daily_invite_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Сколько инвайтов отправлено сегодня (сбрасывается в UTC 00:00)",
    )
    daily_invite_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Когда в последний раз сбрасывался дневной счётчик",
    )
    total_invites: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Сколько инвайтов всего отправлено этим аккаунтом",
    )
    total_invite_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Сколько ошибок при инвайтинге произошло",
    )
    total_floodwaits: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Сколько раз аккаунт получал FloodWait",
    )
    success_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        doc="Доля успешных инвайтов (0.0 .. 1.0)",
    )

    # ==================== Metadata (JSONB) ====================
    # Используем имя 'metadata' — но в SQLAlchemy это зарезервировано,
    # поэтому физически колонка называется 'extra_data'.
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        doc=(
            "Произвольные данные (premium-флаги, device_model, system_version, "
            "app_version, lang_code и т.п.)"
        ),
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Произвольные заметки владельца",
    )

    # ==================== Relationships ====================
    owner: Mapped["User"] = relationship(
        back_populates="accounts",
        lazy="selectin",
        doc="Владелец аккаунта",
    )
    proxy: Mapped["Proxy | None"] = relationship(
        back_populates="accounts",
        lazy="selectin",
        doc="Прокси, через который подключается аккаунт",
    )
    tasks: Mapped[list["InviteTask"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="select",
        doc="Задачи инвайтинга, привязанные к этому аккаунту",
    )

    # ==================== Computed helpers ====================
    @property
    def account_metadata(self) -> dict[str, Any]:
        """Алиас для extra_data (для совместимости с API-контрактом)."""
        return self.extra_data or {}

    @property
    def is_banned(self) -> bool:
        """Забанен ли аккаунт (по статусу или banned_until в будущем)."""
        if self.status == "banned":
            return True
        if self.banned_until and self.banned_until > datetime.utcnow():
            return True
        return False

    @property
    def is_in_cooldown(self) -> bool:
        """Действует ли сейчас cooldown."""
        if self.status == "cooldown":
            if self.cooldown_until is None:
                return True
            return self.cooldown_until > datetime.utcnow()
        return False

    @property
    def display_name(self) -> str:
        """Лучшее отображение аккаунта для UI: label / phone / username."""
        return self.label or self.phone or self.username or self.session_name

    @property
    def fingerprint(self) -> str:
        """Короткий отпечаток для логов (без раскрытия данных)."""
        return fingerprint_account(self.phone, self.api_id, self.session_name)

    def __repr__(self) -> str:
        return (
            f"<Account id={self.id} label={self.label!r} "
            f"phone={self.phone!r} status={self.status!r} fp={self.fingerprint}>"
        )

    def __str__(self) -> str:
        return f"Account({self.display_name}, status={self.status})"
