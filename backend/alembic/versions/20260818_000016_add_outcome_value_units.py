"""add explicit outcome value units

Revision ID: 20260818_000016
Revises: 20260818_000015
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260818_000016"
down_revision = "20260818_000015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outcome_events",
        sa.Column("value_unit", sa.String(length=16), nullable=True),
    )
    op.create_index(
        "ix_outcome_events_value_unit",
        "outcome_events",
        ["value_unit"],
    )
    op.create_index(
        "ix_outcome_events_stage_type_value_unit",
        "outcome_events",
        ["stage", "event_type", "value_unit"],
    )


def downgrade() -> None:
    op.drop_index("ix_outcome_events_stage_type_value_unit", table_name="outcome_events")
    op.drop_index("ix_outcome_events_value_unit", table_name="outcome_events")
    op.drop_column("outcome_events", "value_unit")
