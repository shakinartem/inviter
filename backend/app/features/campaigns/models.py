from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.features.auth.models import User
    from app.features.parser.models import ParsedChat


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    owner_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    source_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_chat_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    target_chat_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_delay_from: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    invite_delay_to: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # NOTE: back_populates="campaigns" removed because User model no longer has
    # a `campaigns` relationship. The old Campaign model is kept for backward
    # compatibility only (table exists, but no runtime relationships use it).
    owner: Mapped["User"] = relationship()
    # NOTE: parsed_chats relationship removed — it's now handled by InviteCampaign/ParsedChat.
    # The old Campaign model is kept for backward compatibility only.
