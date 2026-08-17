from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AudienceSegment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audience_segments"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    criteria: Mapped[dict] = mapped_column(JSON, nullable=False)
    criteria_version: Mapped[str] = mapped_column(String(32), default="segment-v1", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    refresh_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    members: Mapped[list["AudienceSegmentMember"]] = relationship(
        back_populates="segment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_audience_segment_owner_name"),
        Index("ix_audience_segments_owner_active", "owner_id", "is_active"),
    )


class AudienceSegmentMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audience_segment_members"

    segment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audience_segments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    audience_member_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audience_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    activity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    intent_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    strongest_signal_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    match_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    refresh_sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    segment: Mapped[AudienceSegment] = relationship(back_populates="members")
    audience_member = relationship("AudienceMember")

    __table_args__ = (
        UniqueConstraint("segment_id", "audience_member_id", name="uq_audience_segment_member"),
        Index("ix_audience_segment_members_segment_readiness", "segment_id", "readiness_score"),
    )


class CampaignAudienceSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_audience_sources"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invite_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audience_segments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False)
    criteria_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    segment_refresh_sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    segment = relationship("AudienceSegment")
    campaign = relationship("InviteCampaign")
    members: Mapped[list["CampaignAudienceMember"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", name="uq_campaign_audience_source_campaign"),
    )


class CampaignAudienceMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_audience_members"

    campaign_source_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("campaign_audience_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    audience_member_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audience_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    intent_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    strongest_signal_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    match_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    source: Mapped[CampaignAudienceSource] = relationship(back_populates="members")
    audience_member = relationship("AudienceMember")

    __table_args__ = (
        UniqueConstraint("campaign_source_id", "audience_member_id", name="uq_campaign_audience_member"),
    )
