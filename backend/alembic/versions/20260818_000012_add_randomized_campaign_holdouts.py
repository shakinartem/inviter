"""add randomized campaign holdouts

Revision ID: 20260818_000012
Revises: 20260818_000011
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_000012"
down_revision = "20260818_000011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("holdout_percentage", sa.Float(), nullable=False),
        sa.Column("assignment_salt", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="configured"),
        sa.Column("action_budget", sa.Integer(), nullable=True),
        sa.Column("candidate_pool_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("treatment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("holdout_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id"),
    )
    op.create_index("ix_campaign_experiments_owner_id", "campaign_experiments", ["owner_id"])
    op.create_index("ix_campaign_experiments_campaign_id", "campaign_experiments", ["campaign_id"], unique=True)
    op.create_index("ix_campaign_experiments_status", "campaign_experiments", ["status"])
    op.create_index("ix_campaign_experiments_owner_status", "campaign_experiments", ["owner_id", "status"])

    op.create_table(
        "experiment_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant", sa.String(length=16), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experiment_id"], ["campaign_experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "audience_member_id", name="uq_experiment_assignment_member"),
    )
    op.create_index("ix_experiment_assignments_owner_id", "experiment_assignments", ["owner_id"])
    op.create_index("ix_experiment_assignments_experiment_id", "experiment_assignments", ["experiment_id"])
    op.create_index("ix_experiment_assignments_campaign_id", "experiment_assignments", ["campaign_id"])
    op.create_index("ix_experiment_assignments_audience_member_id", "experiment_assignments", ["audience_member_id"])
    op.create_index("ix_experiment_assignments_variant", "experiment_assignments", ["variant"])
    op.create_index("ix_experiment_assignments_campaign_variant", "experiment_assignments", ["campaign_id", "variant"])


def downgrade() -> None:
    op.drop_table("experiment_assignments")
    op.drop_table("campaign_experiments")
