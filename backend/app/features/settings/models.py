from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class SiteSettings(Base):
    __tablename__ = "site_settings"
    __table_args__ = (
        CheckConstraint("language IN ('ru', 'en')", name="ck_site_settings_language"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=SINGLETON_ID
    )
    language: Mapped[str] = mapped_column(
        String(5), default="ru", nullable=False, comment="Interface language: ru or en"
    )
    site_name: Mapped[Optional[str]] = mapped_column(
        String(255), default="Inviter Pro", nullable=True, comment="Site display name"
    )
    logo_path: Mapped[Optional[str]] = mapped_column(
        String(500), default=None, nullable=True, comment="Path to uploaded logo"
    )
    help_text: Mapped[Optional[str]] = mapped_column(
        Text, default=None, nullable=True, comment="Help / instruction text in markdown"
    )
    system_config: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=None, nullable=True, comment="Arbitrary system settings as JSON"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )
