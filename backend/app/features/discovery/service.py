from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.connectors.defaults import register_default_connectors
from app.features.connectors.registry import ConnectorRegistry, connector_registry
from app.features.parser.models import ParsedChat
from app.features.parser.schemas import ParsedChatCreate, ParserSearchRequest
from app.features.parser.service import ParserService


class DiscoveryService:
    """Platform-aware discovery entrypoint.

    Telegram discovery is handled through the connector registry. Legacy catalog
    sources (TGStat/Telemetr) remain behind ParserService until they get their own
    connector adapters.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        redis: Any | None = None,
        registry: ConnectorRegistry | None = None,
    ) -> None:
        self.session = session
        self.redis = redis
        register_default_connectors()
        self.registry = registry or connector_registry
        self.legacy_parser = ParserService(redis=redis)

    async def search(
        self,
        *,
        request: ParserSearchRequest,
        owner_id: UUID,
    ) -> list[ParsedChat]:
        if request.source != "telegram":
            return await self.legacy_parser.search_chats(
                request=request,
                owner_id=owner_id,
                db_session=self.session,
            )

        account = await self._get_active_account(owner_id)
        if account is None:
            raise ValueError("No active Telegram account available for discovery")

        connector = self.registry.get("telegram")
        communities = await connector.discover_communities(
            request.query,
            account=account,
            limit=request.limit,
            filters={
                "chat_type": request.chat_type,
                "language": request.language,
                "country": request.country,
            },
        )

        records: list[ParsedChatCreate] = []
        for community in communities:
            participants = community.get("participants_count")
            if participants is not None:
                if participants < request.min_participants:
                    continue
                if request.max_participants and participants > request.max_participants:
                    continue

            raw_external_id = community.get("external_id")
            if raw_external_id is None:
                continue
            try:
                numeric_id = int(raw_external_id)
            except (TypeError, ValueError):
                continue

            metadata = dict(community.get("raw") or {})
            metadata.update(
                {
                    "platform": "telegram",
                    "external_id": str(raw_external_id),
                    "discovery_query": request.query,
                }
            )

            records.append(
                ParsedChatCreate(
                    chat_id=-abs(numeric_id),
                    username=community.get("username"),
                    title=community.get("title"),
                    access_hash=community.get("access_hash"),
                    chat_type=community.get("type"),
                    participants_count=participants,
                    is_public=bool(community.get("username")),
                    source="telegram_search",
                    niche=request.query,
                    language=request.language,
                    country=request.country,
                    extra_data=metadata,
                )
            )

        return await self.legacy_parser.save_parsed_chats(
            chats=records,
            owner_id=owner_id,
            db_session=self.session,
        )

    async def close(self) -> None:
        await self.legacy_parser.close()

    async def _get_active_account(self, owner_id: UUID) -> Account | None:
        result = await self.session.execute(
            select(Account)
            .where(
                Account.owner_id == owner_id,
                Account.is_active.is_(True),
                Account.status == "active",
            )
            .order_by(Account.last_used_at.asc().nullsfirst())
            .limit(1)
        )
        return result.scalar_one_or_none()
