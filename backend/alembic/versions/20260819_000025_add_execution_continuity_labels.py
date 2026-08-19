"""add execution continuity label fields

Revision ID: 20260819_000025
Revises: 20260819_000024
Create Date: 2026-08-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260819_000025"
down_revision = "20260819_000024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("execution_sla_forecasts", sa.Column("actual_met_continuity", sa.Boolean(), nullable=True))
    op.add_column("execution_sla_forecasts", sa.Column("continuity_windows_total", sa.Integer(), nullable=True))
    op.add_column("execution_sla_forecasts", sa.Column("continuity_windows_met", sa.Integer(), nullable=True))
    op.add_column("execution_sla_forecasts", sa.Column("actual_continuity_rate", sa.Float(), nullable=True))
    op.add_column(
        "execution_sla_forecasts",
        sa.Column("continuity_label_notes", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("execution_sla_forecasts", "continuity_label_notes")
    op.drop_column("execution_sla_forecasts", "actual_continuity_rate")
    op.drop_column("execution_sla_forecasts", "continuity_windows_met")
    op.drop_column("execution_sla_forecasts", "continuity_windows_total")
    op.drop_column("execution_sla_forecasts", "actual_met_continuity")
