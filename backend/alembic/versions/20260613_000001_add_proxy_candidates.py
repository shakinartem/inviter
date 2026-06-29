"""add proxy_candidates table for MTProto import

Revision ID: 20260613_000001
Revises: a1b2c3d4e5f6
Create Date: 2026-06-13 16:45:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260613_000001"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxy_candidates",
        sa.Column("proxy_type", sa.String(20), nullable=False, server_default="mtproto"),
        sa.Column("host", sa.String(255), nullable=False, index=True),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("secret", sa.String(255), nullable=True),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="manual_text"),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new", index=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"],
            name="fk_proxy_candidates_owner_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_proxy_candidates"),
        sa.CheckConstraint("proxy_type IN ('mtproto', 'http', 'socks5')", name="ck_proxy_candidates_proxy_type"),
        sa.CheckConstraint("source_type IN ('manual_text', 'telegram_channel')", name="ck_proxy_candidates_source_type"),
        sa.CheckConstraint("status IN ('new', 'checking', 'alive', 'dead', 'approved', 'rejected')", name="ck_proxy_candidates_status"),
        sa.CheckConstraint("port >= 1 AND port <= 65535", name="ck_proxy_candidates_port"),
    )
    op.create_index("ix_proxy_candidates_owner_id", "proxy_candidates", ["owner_id"])


def downgrade() -> None:
    op.drop_table("proxy_candidates")