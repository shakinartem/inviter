"""add automatic outcome observer cursors

Revision ID: 20260817_000010
Revises: 20260817_000009
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_000010"
down_revision = "20260817_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outcome_observer_cursors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("messages_seen", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("outcomes_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", name="uq_outcome_observer_cursor_campaign"),
    )
    op.create_index("ix_outcome_observer_cursors_owner_id", "outcome_observer_cursors", ["owner_id"])
    op.create_index("ix_outcome_observer_cursors_platform", "outcome_observer_cursors", ["platform"])
    op.create_index("ix_outcome_observer_cursors_status", "outcome_observer_cursors", ["status"])
    op.create_index("ix_outcome_observer_cursors_last_run_at", "outcome_observer_cursors", ["last_run_at"])
    op.create_index(
        "ix_outcome_observer_cursors_owner_status",
        "outcome_observer_cursors",
        ["owner_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("outcome_observer_cursors")
