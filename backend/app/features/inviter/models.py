from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.features.accounts.models import Account
    from app.features.proxies.models import Proxy
    from app.features.auth.models import User
    from app.features.parser.models import ParsedChat


class InviteCampaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invite_campaigns"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="draft", nullable=False, index=True
    )  # draft, active, paused, completed, failed

    # Source of users to invite
    source_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_chat_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(32), default="chat", nullable=False
    )  # chat, parsed_list, uploaded_list

    # Target chat where to invite
    target_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_chat_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_chat_username: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Invite settings
    daily_limit_per_account: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    invite_delay_min: Mapped[int] = mapped_column(
        Integer, default=45, nullable=False
    )  # seconds
    invite_delay_max: Mapped[int] = mapped_column(
        Integer, default=180, nullable=False
    )  # seconds
    pause_after_every: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False
    )  # pause after N invites
    pause_duration_min: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False
    )  # minutes
    pause_duration_max: Mapped[int] = mapped_column(
        Integer, default=15, nullable=False
    )  # minutes

    # Warmup settings
    warmup_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    warmup_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    warmup_limit_factor: Mapped[float] = mapped_column(
        Float, default=0.2, nullable=False
    )  # multiplier for daily limit during warmup

    # Additional options
    only_add_contacts: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    add_to_contacts_first: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )  # add to contacts before inviting

    # Blacklist settings (stored as comma-separated strings or arrays)
    blacklist_usernames: Mapped[str | None] = mapped_column(Text, nullable=True)
    blacklist_user_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Campaign timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Source chat (ParsedChat) — for parsed_list source_type
    source_parsed_chat_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("parsed_chats.id"), nullable=True,
        doc="ID ParsedChat, из которого берутся пользователи"
    )

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="invite_campaigns")
    tasks: Mapped[list["InviteTask"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    # NOTE: parsed_chat_relation removed — link is via source_parsed_chat_id FK only.

    __table_args__ = (
        Index("ix_invite_campaigns_owner_id", "owner_id"),
    )

    def __repr__(self) -> str:
        return f"<InviteCampaign {self.title} (status={self.status})>"


class InviteTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invite_tasks"

    campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invite_campaigns.id"), nullable=False, index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    proxy_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("proxies.id"), nullable=True, index=True
    )

    # Target user to invite
    target_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    target_username: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Task status and tracking
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False, index=True
    )  # pending, processing, success, failed, floodwait, paused
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    campaign: Mapped["InviteCampaign"] = relationship(back_populates="tasks")
    account: Mapped["Account"] = relationship()
    proxy: Mapped["Proxy | None"] = relationship()
    logs: Mapped[list["InviteLog"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", "target_user_id", name="uq_invite_tasks_campaign_target_user"),
    )

    def __repr__(self) -> str:
        return f"<InviteTask {self.target_user_id} (status={self.status})>"


class InviteLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invite_logs"

    invite_task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invite_tasks.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'add_contact', 'invite_to_chat', 'check_user'
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    task: Mapped["InviteTask"] = relationship(back_populates="logs")

    __table_args__ = (
        Index("ix_invite_logs_action", "action"),
        Index("ix_invite_logs_success", "success"),
    )

    def __repr__(self) -> str:
        return f"<InviteLog {self.action} (success={self.success})>"
