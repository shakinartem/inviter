"""Add source_parsed_chat_id to invite_campaigns

Revision ID: 20260629_000001
Revises: 20260613_000002
Create Date: 2026-06-29 17:05:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


revision = "20260629_000001"
down_revision = "20260613_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add source_parsed_chat_id column to invite_campaigns
    op.add_column(
        "invite_campaigns",
        sa.Column(
            "source_parsed_chat_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("parsed_chats.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_invite_campaigns_source_parsed_chat_id",
        "invite_campaigns",
        ["source_parsed_chat_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_invite_campaigns_source_parsed_chat_id")
    op.drop_column("invite_campaigns", "source_parsed_chat_id")