from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExecutionSLAForecastSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Prediction-time execution snapshot plus mature observed outcome label."""

    __tablename__ = "execution_sla_forecasts"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invite_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    remaining_actions: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    target_sla: Mapped[float] = mapped_column(Float, nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_quality: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    current_reserve_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_reserve_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_modelled_continuity_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_conservative_continuity_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    normal_daily_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    emergency_daily_capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    input_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    scenarios_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)

    # `actual_met_sla` calibrates fixed-workload completion probability for the
    # CURRENT reserve scenario. It does not pretend to label schedule continuity.
    actual_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_met_sla: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    label_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    queue_eligible_at_forecast: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    actual_successful_actions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_hard_failure_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label_finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    label_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_execution_sla_forecasts_owner_created", "owner_id", "created_at"),
        Index("ix_execution_sla_forecasts_campaign_created", "campaign_id", "created_at"),
    )
