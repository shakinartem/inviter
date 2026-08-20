"""add execution reserve capacity configuration

Revision ID: 20260819_000020
Revises: 20260819_000019
Create Date: 2026-08-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260819_000020"
down_revision = "20260819_000019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invite_campaigns",
        sa.Column(
            "reserve_capacity_percentage",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_invite_campaigns_reserve_capacity_percentage",
        "invite_campaigns",
        "reserve_capacity_percentage >= 0 AND reserve_capacity_percentage <= 50",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_invite_campaigns_reserve_capacity_percentage",
        "invite_campaigns",
        type_="check",
    )
    op.drop_column("invite_campaigns", "reserve_capacity_percentage")
