"""add proxies.secret column for MTProto proxy support

Revision ID: 20260701_000001
Revises: 20260630_000001
Create Date: 2026-07-01 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260701_000001"
down_revision: Union[str, None] = "20260630_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "proxies",
        sa.Column("secret", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("proxies", "secret")