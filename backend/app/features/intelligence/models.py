from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CommunitySnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_snapshots"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parsed_chat_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("parsed_chats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    participants_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_1d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    messages_1d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    messages_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unique_authors_1d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unique_authors_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bot_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    spam_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    growth_rate_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    chat = relationship("ParsedChat")

    __table_args__ = (
        Index("ix_community_snapshots_chat_captured", "parsed_chat_id", "captured_at"),
    )


class AudienceMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audience_members"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_scam: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_fake: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    activity_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    intent_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    memberships: Mapped[list["CommunityMembership"]] = relationship(
        back_populates="member", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "platform", "external_user_id", name="uq_audience_member_identity"),
        Index("ix_audience_members_owner_readiness", "owner_id", "readiness_score"),
    )


class CommunityMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_memberships"

    audience_member_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audience_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parsed_chat_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("parsed_chats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    messages_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    messages_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    member: Mapped[AudienceMember] = relationship(back_populates="memberships")
    chat = relationship("ParsedChat")

    __table_args__ = (
        UniqueConstraint("audience_member_id", "parsed_chat_id", name="uq_member_community"),
    )
