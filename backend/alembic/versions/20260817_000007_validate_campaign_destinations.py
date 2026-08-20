"""enforce resolvable Telegram campaign destinations

Revision ID: 20260817_000007
Revises: 20260817_000006
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op


revision = "20260817_000007"
down_revision = "20260817_000006"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "ck_campaign_destination_resolvable_telegram"


def upgrade() -> None:
    # Backfilled legacy destinations may point at a private supergroup for which
    # the historical parser never captured access_hash. Keeping such a row would
    # make the new scheduler believe it is reproducibly resolvable. Drop only the
    # derived canonical row; the legacy InviteCampaign remains intact and can be
    # repaired by syncing the destination community again.
    op.execute(
        """
        DELETE FROM campaign_destinations
        WHERE platform = 'telegram'
          AND community_type IN ('channel', 'supergroup')
          AND COALESCE(username, '') = ''
          AND COALESCE(access_hash, '') = ''
        """
    )

    # A basic Telegram group can be addressed by chat id. A private supergroup
    # (MTProto Channel) requires either its username or access_hash. Without one,
    # another worker account cannot reliably resolve the destination entity.
    op.create_check_constraint(
        CONSTRAINT_NAME,
        "campaign_destinations",
        """
        NOT (
            platform = 'telegram'
            AND community_type IN ('channel', 'supergroup')
            AND COALESCE(username, '') = ''
            AND COALESCE(access_hash, '') = ''
        )
        """,
    )


def downgrade() -> None:
    op.drop_constraint(
        CONSTRAINT_NAME,
        "campaign_destinations",
        type_="check",
    )
