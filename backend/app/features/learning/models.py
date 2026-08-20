from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ActionFeatureSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable model features as they were known when an action was attempted."""

    __tablename__ = "action_feature_snapshots"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("action_jobs.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invite_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    audience_member_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audience_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)

    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    first_transport_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    activity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    intent_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    signal_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    strongest_signal_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intent_model_versions: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    feature_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    snapshot_version: Mapped[str] = mapped_column(
        String(64), default="action-feature-v1", nullable=False
    )

    action_job = relationship("ActionJob")
    campaign = relationship("InviteCampaign")
    audience_member = relationship("AudienceMember")

    __table_args__ = (
        UniqueConstraint("action_job_id", name="uq_action_feature_snapshot_job"),
        Index("ix_action_feature_snapshots_owner_captured", "owner_id", "captured_at"),
    )


class OutcomeEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only observed result attributed to an action or randomized unit."""

    __tablename__ = "outcome_events"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_job_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("action_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    experiment_assignment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("experiment_assignments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invite_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    audience_member_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audience_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)

    stage: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    external_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    action_job = relationship("ActionJob")
    experiment_assignment = relationship("ExperimentAssignment")
    campaign = relationship("InviteCampaign")
    audience_member = relationship("AudienceMember")

    __table_args__ = (
        UniqueConstraint("owner_id", "dedupe_key", name="uq_outcome_event_owner_dedupe"),
        Index("ix_outcome_events_stage_type", "stage", "event_type"),
        Index("ix_outcome_events_member_observed", "audience_member_id", "observed_at"),
        Index("ix_outcome_events_campaign_stage", "campaign_id", "stage"),
        Index("ix_outcome_events_assignment_stage", "experiment_assignment_id", "stage"),
    )