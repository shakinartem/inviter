from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CampaignPreflightDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable launch-time decision snapshot plus factual execution label."""

    __tablename__ = "campaign_preflight_decisions"

    owner_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("invite_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action_budget_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    action_budget_executable: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_jobs: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline_days: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    required_daily_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    destination_ready: Mapped[bool] = mapped_column(Boolean, nullable=False)
    frozen_cohort_size: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_candidate_pool: Mapped[int] = mapped_column(Integer, nullable=False)
    required_candidate_pool: Mapped[int] = mapped_column(Integer, nullable=False)
    holdout_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    eligible_accounts: Mapped[int] = mapped_column(Integer, nullable=False)
    quarantined_accounts: Mapped[int] = mapped_column(Integer, nullable=False)
    normal_daily_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    emergency_daily_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_failover_headroom: Mapped[int] = mapped_column(Integer, nullable=False)
    n_minus_one_surviving_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    n_minus_one_covers_required_rate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    model_health_status: Mapped[str] = mapped_column(String(32), nullable=False)
    active_calibrator_version: Mapped[str | None] = mapped_column(String(96), nullable=True)
    account_ids_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    checks_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    warnings_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    plan_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    tracked_job_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    launched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    label_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    actual_successful_jobs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_failed_jobs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_cancelled_jobs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_completion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_met_execution_plan: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    label_finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    label_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_campaign_preflight_decisions_owner_created", "owner_id", "created_at"),
    )
