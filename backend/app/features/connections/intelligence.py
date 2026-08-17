from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.features.accounts.credentials import credential_vault
from app.features.accounts.models import Account
from app.features.connections.service import ConnectorAccountContext
from app.features.intelligence.models import AudienceMember
from app.features.intelligence.service import IntelligenceService


class ConnectionAwareIntelligenceService(IntelligenceService):
    """Bind community enrichment to an account from the same platform."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._platform_hint: str | None = None

    async def enrich_community(
        self,
        *,
        owner_id: UUID,
        parsed_chat_id: UUID,
        account_id: UUID | None = None,
        member_limit: int = 2_000,
        message_limit: int = 10_000,
        lookback_days: int = 30,
        relevance_score: float | None = None,
    ) -> dict[str, Any]:
        chat = await self._get_chat(owner_id, parsed_chat_id)
        if chat is None:
            raise ValueError("Community not found")
        self._platform_hint = self._resolve_platform(chat)
        try:
            return await super().enrich_community(
                owner_id=owner_id,
                parsed_chat_id=parsed_chat_id,
                account_id=account_id,
                member_limit=member_limit,
                message_limit=message_limit,
                lookback_days=lookback_days,
                relevance_score=relevance_score,
            )
        finally:
            self._platform_hint = None

    async def _get_account(
        self,
        owner_id: UUID,
        account_id: UUID | None,
    ) -> Account | ConnectorAccountContext | None:
        stmt = select(Account).where(
            Account.owner_id == owner_id,
            Account.is_active.is_(True),
            Account.status == "active",
        )
        if self._platform_hint:
            stmt = stmt.where(Account.platform == self._platform_hint)
        if account_id is not None:
            stmt = stmt.where(Account.id == account_id)
        stmt = stmt.order_by(
            Account.health_score.desc(),
            Account.last_used_at.asc().nullsfirst(),
        ).limit(1)
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if account is None:
            return None

        # Legacy Telegram manager expects the ORM Account instance directly.
        if account.platform == "telegram":
            return account
        return ConnectorAccountContext(
            account=account,
            credentials=credential_vault.decrypt(account.credential_payload_encrypted),
        )

    async def _upsert_members(
        self,
        *,
        owner_id: UUID,
        platform: str,
        members: list[dict[str, Any]],
        activity: dict[str, dict[str, Any]],
    ) -> dict[str, AudienceMember]:
        profiles = await super()._upsert_members(
            owner_id=owner_id,
            platform=platform,
            members=members,
            activity=activity,
        )

        # Keep platform-specific transport identifiers (Telegram access_hash,
        # future connector IDs, etc.) out of generic profile columns while still
        # making actions reproducible across worker accounts.
        for member_data in members:
            raw_external_id = member_data.get("external_user_id")
            if raw_external_id is None:
                continue
            profile = profiles.get(str(raw_external_id))
            if profile is None:
                continue
            incoming = member_data.get("platform_data")
            if not isinstance(incoming, dict):
                continue
            merged = dict(profile.platform_data or {})
            merged.update({key: value for key, value in incoming.items() if value is not None})
            profile.platform_data = merged or None

        await self.session.flush()
        return profiles
