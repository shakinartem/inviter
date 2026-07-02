"""Create parsed_users table matching SQLAlchemy ParsedUser model

Revision ID: 20260701_000005
Revises: 20260701_000004
Create Date: 2026-07-01 14:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import text


revision = "20260701_000005"
down_revision = "20260701_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parsed_users",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", PG_UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chat_id", PG_UUID(as_uuid=True), sa.ForeignKey("parsed_chats.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("username", sa.String(255), nullable=True, index=True),
        sa.Column("first_name", sa.String(120), nullable=True),
        sa.Column("last_name", sa.String(120), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_scam", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_fake", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("was_online_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("msg_count", sa.Integer(), nullable=True),
    )

    # NOTE: owner_id, chat_id, user_id, username already have index=True
    # in the column definitions above, so no separate create_index needed.
    # Only create additional indices that are not covered by column index=True.
    # (All indices are already covered by column definitions.)


def downgrade() -> None:
    op.drop_table("parsed_users")
