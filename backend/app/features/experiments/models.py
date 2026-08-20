from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CampaignExperiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_experiments"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invite_campaigns.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    holdout_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    assignment_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="configured", index=True)
    action_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_pool_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    treatment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    holdout_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assignments: Mapped[list["ExperimentAssignment"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_campaign_experiments_owner_status", "owner_id", "status"),
    )


class ExperimentAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiment_assignments"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experiment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("campaign_experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invite_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    audience_member_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audience_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    experiment: Mapped[CampaignExperiment] = relationship(back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("experiment_id", "audience_member_id", name="uq_experiment_assignment_member"),
        Index("ix_experiment_assignments_campaign_variant", "campaign_id", "variant"),
    )
