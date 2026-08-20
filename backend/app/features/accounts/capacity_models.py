from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AccountCapacitySnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable operational risk/capacity assessment for a connected account."""

    __tablename__ = "account_capacity_snapshots"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    health_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    capacity_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    suggested_daily_capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    attempts_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successes_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    account_errors_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_errors_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    floodwaits_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    peer_floods_7d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    connector_errors_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queued_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    eligible: Mapped[bool] = mapped_column(default=True, nullable=False)
    next_safe_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reasons: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    account = relationship("Account")

    __table_args__ = (
        Index("ix_account_capacity_snapshots_account_calculated", "account_id", "calculated_at"),
        Index("ix_account_capacity_snapshots_owner_platform", "owner_id", "platform", "calculated_at"),
    )
