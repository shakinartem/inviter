from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.features.auth.models import User
    from app.features.inviter.models import InviteTask
    from app.features.proxies.models import Proxy


ACCOUNT_STATUSES: tuple[str, ...] = (
    "active",
    "idle",
    "limited",
    "cooldown",
    "banned",
    "inactive",
    "error",
)


def generate_session_name(prefix: str = "acc") -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def fingerprint_account(
    phone: str | None,
    api_id: int | None,
    session_name: str | None,
    *,
    platform: str = "telegram",
    external_account_id: str | None = None,
) -> str:
    raw = (
        f"{platform}|{external_account_id or ''}|{phone or ''}|"
        f"{api_id or ''}|{session_name or ''}"
    ).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:8]


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Connected messenger account.

    Telegram legacy fields remain on the table for backwards compatibility.
    Platform-neutral routing, identity, capabilities and encrypted credentials are
    used by new connectors. Secret credential material must only be written to
    ``credential_payload_encrypted`` through CredentialVault.
    """

    __tablename__ = "accounts"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proxy_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("proxies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Platform-neutral identity / auth routing.
    platform: Mapped[str] = mapped_column(
        String(32), default="telegram", nullable=False, index=True
    )
    external_account_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    auth_type: Mapped[str] = mapped_column(
        String(32), default="session", nullable=False
    )
    credential_payload_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    capabilities: Mapped[dict[str, bool] | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    health_score: Mapped[float] = mapped_column(
        Float, default=100.0, nullable=False
    )

    label: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(
        String(32), nullable=True, unique=True, index=True
    )

    # Telegram session/API credentials. Optional for non-Telegram connectors.
    session_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    api_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Legacy Telegram profile fields. Generic connectors populate common profile
    # fields and external_account_id instead of depending on telegram_user_id.
    telegram_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, unique=True, index=True
    )
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), default="idle", nullable=False, index=True
    )
    status_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    banned_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    daily_invite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_invite_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_invites: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_invite_errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_floodwaits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, default=None)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped["User"] = relationship(back_populates="accounts", lazy="selectin")
    proxy: Mapped["Proxy | None"] = relationship(back_populates="accounts", lazy="selectin")
    tasks: Mapped[list["InviteTask"]] = relationship(
        back_populates="account", cascade="all, delete-orphan", lazy="select"
    )

    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "platform",
            "external_account_id",
            name="uq_accounts_owner_platform_external",
        ),
        Index("ix_accounts_owner_platform", "owner_id", "platform"),
    )

    @property
    def account_metadata(self) -> dict[str, Any]:
        return self.extra_data or {}

    @property
    def is_banned(self) -> bool:
        if self.status == "banned":
            return True
        if self.banned_until and self.banned_until > datetime.utcnow():
            return True
        return False

    @property
    def is_in_cooldown(self) -> bool:
        if self.status == "cooldown":
            if self.cooldown_until is None:
                return True
            return self.cooldown_until > datetime.utcnow()
        return False

    @property
    def display_name(self) -> str:
        return (
            self.label
            or self.username
            or self.phone
            or self.external_account_id
            or self.session_name
            or self.platform
        )

    @property
    def fingerprint(self) -> str:
        return fingerprint_account(
            self.phone,
            self.api_id,
            self.session_name,
            platform=self.platform,
            external_account_id=self.external_account_id,
        )

    def __repr__(self) -> str:
        return (
            f"<Account id={self.id} platform={self.platform!r} label={self.label!r} "
            f"status={self.status!r} fp={self.fingerprint}>"
        )

    def __str__(self) -> str:
        return f"Account({self.platform}:{self.display_name}, status={self.status})"
