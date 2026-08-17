from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.features.accounts.models import Account
from app.features.orchestration.service import OrchestrationService


class ConnectionAwareOrchestrationService(OrchestrationService):
    """Constrain legacy direct-invite campaigns to compatible accounts.

    The current InviteCampaign destination model is still Telegram-specific, so
    the allocator must not select Discord (or future) connections just because
    they are healthy and active. When Campaign becomes platform-neutral this
    override can become a generic `platform` argument in the base allocator.
    """

    async def _get_accounts(
        self,
        owner_id: UUID,
        account_ids: list[UUID] | None,
    ) -> list[Account]:
        stmt = select(Account).where(
            Account.owner_id == owner_id,
            Account.platform == "telegram",
            Account.is_active.is_(True),
            Account.status == "active",
        )
        if account_ids:
            stmt = stmt.where(Account.id.in_(account_ids))
        result = await self.session.execute(
            stmt.order_by(
                Account.health_score.desc(),
                Account.last_used_at.asc().nullsfirst(),
            )
        )
        return list(result.scalars().all())
