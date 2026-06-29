"""add invite task campaign target dedup

Revision ID: 20260629_000002
Revises: 20260629_000001
Create Date: 2026-06-29 21:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260629_000002"
down_revision: Union[str, None] = "20260629_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_invite_tasks_campaign_target_user",
        "invite_tasks",
        ["campaign_id", "target_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_invite_tasks_campaign_target_user",
        "invite_tasks",
        type_="unique",
    )
