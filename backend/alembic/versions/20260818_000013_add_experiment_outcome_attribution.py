"""add experiment assignment attribution to outcomes

Revision ID: 20260818_000013
Revises: 20260818_000012
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_000013"
down_revision = "20260818_000012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outcome_events",
        sa.Column("experiment_assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_outcome_events_experiment_assignment_id",
        "outcome_events",
        "experiment_assignments",
        ["experiment_assignment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_outcome_events_experiment_assignment_id",
        "outcome_events",
        ["experiment_assignment_id"],
    )
    op.create_index(
        "ix_outcome_events_assignment_stage",
        "outcome_events",
        ["experiment_assignment_id", "stage"],
    )


def downgrade() -> None:
    op.drop_index("ix_outcome_events_assignment_stage", table_name="outcome_events")
    op.drop_index("ix_outcome_events_experiment_assignment_id", table_name="outcome_events")
    op.drop_constraint(
        "fk_outcome_events_experiment_assignment_id",
        "outcome_events",
        type_="foreignkey",
    )
    op.drop_column("outcome_events", "experiment_assignment_id")
