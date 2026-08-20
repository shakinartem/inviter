from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CapacityAllocationPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "capacity_allocation_plans"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    total_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    allocation_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="decision_grade")
    require_positive_conservative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="frozen", index=True)
    evidence_version: Mapped[str] = mapped_column(String(64), nullable=False, default="causal-allocation-v1")

    offers_considered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_offers_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allocated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unallocated_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expected_incremental_outcomes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    conservative_incremental_outcomes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    upside_incremental_outcomes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    replicated_context_coverage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    global_prior_status: Mapped[str] = mapped_column(String(32), nullable=False)
    global_prior_lift: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    global_prior_i_squared: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    candidate_pool_capped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    assignments: Mapped[list["CapacityAllocationAssignment"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_capacity_allocation_plans_owner_frozen", "owner_id", "frozen_at"),
    )


class CapacityAllocationAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "capacity_allocation_assignments"

    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("capacity_allocation_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audience_segments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    audience_member_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audience_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    allocation_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    segment_refresh_sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    activity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    intent_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    strongest_signal_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    match_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    evidence_source: Mapped[str] = mapped_column(String(32), nullable=False)
    context_key: Mapped[str] = mapped_column(String(160), nullable=False)
    expected_incremental_probability: Mapped[float] = mapped_column(Float, nullable=False)
    conservative_incremental_probability: Mapped[float] = mapped_column(Float, nullable=False)
    upside_incremental_probability: Mapped[float] = mapped_column(Float, nullable=False)

    plan: Mapped[CapacityAllocationPlan] = relationship(back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("plan_id", "audience_member_id", name="uq_capacity_allocation_plan_member"),
        Index("ix_capacity_allocation_assignments_plan_segment", "plan_id", "segment_id"),
        Index("ix_capacity_allocation_assignments_plan_rank", "plan_id", "allocation_rank"),
    )
