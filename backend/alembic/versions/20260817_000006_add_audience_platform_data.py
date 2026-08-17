"""add audience platform data

Revision ID: 20260817_000006
Revises: 20260817_000005
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_000006"
down_revision = "20260817_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audience_members", sa.Column("platform_data", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("audience_members", "platform_data")
