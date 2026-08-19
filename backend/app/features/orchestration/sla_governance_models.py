from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExecutionSLACalibrator(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned, holdout-validated probability calibrator for execution completion."""

    __tablename__ = "execution_sla_calibrators"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    base_model_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    calibrator_version: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", index=True)

    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    train_count: Mapped[int] = mapped_column(Integer, nullable=False)
    test_count: Mapped[int] = mapped_column(Integer, nullable=False)
    training_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    raw_brier_test: Mapped[float] = mapped_column(Float, nullable=False)
    calibrated_brier_test: Mapped[float] = mapped_column(Float, nullable=False)
    raw_ece_test: Mapped[float] = mapped_column(Float, nullable=False)
    calibrated_ece_test: Mapped[float] = mapped_column(Float, nullable=False)
    raw_bias_test: Mapped[float] = mapped_column(Float, nullable=False)
    calibrated_bias_test: Mapped[float] = mapped_column(Float, nullable=False)

    mapping: Mapped[list] = mapped_column(JSON, nullable=False)
    training_metadata: Mapped[dict] = mapped_column(JSON, nullable=False)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_execution_sla_calibrators_owner_status", "owner_id", "status"),
        Index("ix_execution_sla_calibrators_owner_model", "owner_id", "base_model_version"),
    )
