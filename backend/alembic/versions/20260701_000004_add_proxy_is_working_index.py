"""Add missing index on proxies.is_working to match SQLAlchemy model

Revision ID: 20260701_000004
Revises: 20260701_000003
Create Date: 2026-07-01 12:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260701_000004"
down_revision = "20260701_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_proxies_is_working", "proxies", ["is_working"])


def downgrade() -> None:
    op.drop_index("ix_proxies_is_working", table_name="proxies")