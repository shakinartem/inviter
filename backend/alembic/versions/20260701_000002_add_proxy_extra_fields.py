"""Add missing proxy fields to match SQLAlchemy model

Revision ID: 20260701_000002
Revises: 20260701_000001
Create Date: 2026-07-01 10:10:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260701_000002"
down_revision = "20260701_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proxies", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("proxies", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("proxies", sa.Column("ping_ms", sa.Float(), nullable=True))
    op.add_column(
        "proxies",
        sa.Column("is_working", sa.Boolean(), nullable=True, server_default=None),
    )
    op.add_column("proxies", sa.Column("status_message", sa.String(500), nullable=True))
    op.add_column("proxies", sa.Column("extra_data", sa.JSON(), nullable=True))
    op.add_column("proxies", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("proxies", "notes")
    op.drop_column("proxies", "extra_data")
    op.drop_column("proxies", "status_message")
    op.drop_column("proxies", "is_working")
    op.drop_column("proxies", "ping_ms")
    op.drop_column("proxies", "city")
    op.drop_column("proxies", "country")