"""add account capacity risk snapshots

Revision ID: 20260818_000018
Revises: 20260818_000017
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_000018"
down_revision = "20260818_000017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_capacity_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("health_score", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("capacity_multiplier", sa.Float(), nullable=False),
        sa.Column("suggested_daily_capacity", sa.Integer(), nullable=False),
        sa.Column("attempts_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successes_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("account_errors_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_errors_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("floodwaits_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("peer_floods_7d", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("connector_errors_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("eligible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_safe_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reasons", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_capacity_snapshots_owner_id", "account_capacity_snapshots", ["owner_id"])
    op.create_index("ix_account_capacity_snapshots_account_id", "account_capacity_snapshots", ["account_id"])
    op.create_index("ix_account_capacity_snapshots_platform", "account_capacity_snapshots", ["platform"])
    op.create_index("ix_account_capacity_snapshots_calculated_at", "account_capacity_snapshots", ["calculated_at"])
    op.create_index(
        "ix_account_capacity_snapshots_account_calculated",
        "account_capacity_snapshots",
        ["account_id", "calculated_at"],
    )
    op.create_index(
        "ix_account_capacity_snapshots_owner_platform",
        "account_capacity_snapshots",
        ["owner_id", "platform", "calculated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_capacity_snapshots_owner_platform", table_name="account_capacity_snapshots")
    op.drop_index("ix_account_capacity_snapshots_account_calculated", table_name="account_capacity_snapshots")
    op.drop_index("ix_account_capacity_snapshots_calculated_at", table_name="account_capacity_snapshots")
    op.drop_index("ix_account_capacity_snapshots_platform", table_name="account_capacity_snapshots")
    op.drop_index("ix_account_capacity_snapshots_account_id", table_name="account_capacity_snapshots")
    op.drop_index("ix_account_capacity_snapshots_owner_id", table_name="account_capacity_snapshots")
    op.drop_table("account_capacity_snapshots")
