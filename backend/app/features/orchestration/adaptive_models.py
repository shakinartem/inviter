from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ActionAssignmentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable audit record for one pre-execution account reassignment."""

    __tablename__ = "action_assignment_events"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invite_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("action_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    reason: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    new_scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    job = relationship("ActionJob")
    from_account = relationship("Account", foreign_keys=[from_account_id])
    to_account = relationship("Account", foreign_keys=[to_account_id])

    __table_args__ = (
        Index("ix_action_assignment_events_job_created", "action_job_id", "created_at"),
        Index("ix_action_assignment_events_owner_created", "owner_id", "created_at"),
        Index("ix_action_assignment_events_campaign_created", "campaign_id", "created_at"),
    )
