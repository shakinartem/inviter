"""add site_settings table

Revision ID: a1b2c3d4e5f6
Revises: 20260609_000002
Create Date: 2026-06-12 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "20260609_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("language", sa.String(5), nullable=False, server_default="ru",
                   comment="Interface language: ru or en"),
        sa.Column("site_name", sa.String(255), nullable=True,
                   comment="Site display name"),
        sa.Column("logo_path", sa.String(500), nullable=True,
                   comment="Relative path to uploaded logo"),
        sa.Column("help_text", sa.Text(), nullable=True,
                   comment="Help / instruction text in markdown"),
        sa.Column("system_config", JSONB(), nullable=True,
                   comment="Arbitrary system settings as JSON"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                   server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                   server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("site_settings")