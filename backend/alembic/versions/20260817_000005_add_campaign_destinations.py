"""add canonical campaign destinations

Revision ID: 20260817_000005
Revises: 20260817_000004
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_000005"
down_revision = "20260817_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_destinations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parsed_chat_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("community_type", sa.String(length=32), nullable=True),
        sa.Column("access_hash", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parsed_chat_id"], ["parsed_chats.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", name="uq_campaign_destination_campaign"),
    )
    op.create_index("ix_campaign_destinations_owner_id", "campaign_destinations", ["owner_id"], unique=False)
    op.create_index("ix_campaign_destinations_campaign_id", "campaign_destinations", ["campaign_id"], unique=False)
    op.create_index("ix_campaign_destinations_parsed_chat_id", "campaign_destinations", ["parsed_chat_id"], unique=False)
    op.create_index("ix_campaign_destinations_platform", "campaign_destinations", ["platform"], unique=False)
    op.create_index(
        "ix_campaign_destinations_owner_platform",
        "campaign_destinations",
        ["owner_id", "platform"],
        unique=False,
    )

    # Backfill legacy Telegram campaigns so the new scheduler can resolve their
    # destination through the same platform-neutral table.
    op.execute(
        """
        INSERT INTO campaign_destinations (
            id, created_at, updated_at, owner_id, campaign_id, parsed_chat_id,
            platform, external_id, username, title, community_type, access_hash
        )
        SELECT
            gen_random_uuid(), now(), now(), c.owner_id, c.id, p.id,
            'telegram', ABS(c.target_chat_id)::text, c.target_chat_username,
            c.target_chat_title, p.chat_type, p.access_hash
        FROM invite_campaigns c
        LEFT JOIN parsed_chats p
          ON p.owner_id = c.owner_id
         AND p.chat_id IN (c.target_chat_id, ABS(c.target_chat_id), -ABS(c.target_chat_id))
        WHERE NOT EXISTS (
            SELECT 1 FROM campaign_destinations d WHERE d.campaign_id = c.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_destinations_owner_platform", table_name="campaign_destinations")
    op.drop_index("ix_campaign_destinations_platform", table_name="campaign_destinations")
    op.drop_index("ix_campaign_destinations_parsed_chat_id", table_name="campaign_destinations")
    op.drop_index("ix_campaign_destinations_campaign_id", table_name="campaign_destinations")
    op.drop_index("ix_campaign_destinations_owner_id", table_name="campaign_destinations")
    op.drop_table("campaign_destinations")
