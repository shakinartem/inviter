from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.credentials import credential_vault
from app.features.accounts.models import Account
from app.features.connections.service import ConnectorAccountContext
from app.features.connectors.defaults import register_default_connectors
from app.features.connectors.registry import connector_registry
from app.features.parser.models import ParsedChat


class PlatformDiscoveryService:
    """Discover communities through any installed connector and persist them.

    Existing parser routes remain for legacy catalog sources. This service is the
    connector-native path for Telegram/Discord and future messenger adapters.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        register_default_connectors()

    async def search(
        self,
        *,
        owner_id: UUID,
        platform: str,
        query: str,
        account_id: UUID | None = None,
        limit: int = 100,
        chat_type: str | None = None,
    ) -> list[ParsedChat]:
        platform = platform.strip().lower()
        if not connector_registry.supports(platform):
            raise ValueError(f"Connector is not available for platform: {platform}")
        connector = connector_registry.get(platform)
        if not connector.capabilities.discover_communities:
            raise ValueError(f"{platform} connector does not support community discovery")

        account = await self._account(owner_id, platform, account_id)
        if account is None:
            raise ValueError(f"No active {platform} connection is available")
        context = ConnectorAccountContext(
            account=account,
            credentials=credential_vault.decrypt(account.credential_payload_encrypted),
        )

        communities = await connector.discover_communities(
            query,
            account=context,
            limit=limit,
            filters={"chat_type": chat_type} if chat_type else None,
        )

        saved: list[ParsedChat] = []
        now = datetime.now(timezone.utc)
        for community in communities:
            external_id = str(community.get("external_id") or "").strip()
            if not external_id:
                continue
            chat_id = self._numeric_chat_id(platform, external_id)
            metadata = dict(community.get("raw") or {})
            metadata.update(
                {
                    "platform": platform,
                    "external_id": external_id,
                    "discovery_query": query,
                    "active_participants": community.get("active_participants"),
                }
            )

            existing_result = await self.session.execute(
                select(ParsedChat).where(
                    ParsedChat.owner_id == owner_id,
                    ParsedChat.chat_id == chat_id,
                )
            )
            chat = existing_result.scalar_one_or_none()
            if chat is None:
                chat = ParsedChat(
                    owner_id=owner_id,
                    chat_id=chat_id,
                    username=community.get("username"),
                    title=community.get("title"),
                    description=community.get("description"),
                    access_hash=community.get("access_hash"),
                    chat_type=community.get("type") or "community",
                    participants_count=community.get("participants_count"),
                    active_participants=community.get("active_participants"),
                    category=None,
                    niche=query,
                    tags=None,
                    language=None,
                    country=None,
                    is_public=True,
                    is_active=True,
                    is_restricted=False,
                    source=f"{platform}_connector",
                    last_parsed_at=now,
                    parse_count=1,
                    avg_posts_per_day=None,
                    avg_reach_per_post=None,
                    engagement_rate=None,
                    extra_data=metadata,
                )
                self.session.add(chat)
            else:
                chat.title = community.get("title") or chat.title
                chat.username = community.get("username") or chat.username
                chat.participants_count = community.get("participants_count") or chat.participants_count
                chat.active_participants = community.get("active_participants") or chat.active_participants
                chat.niche = query
                chat.source = f"{platform}_connector"
                chat.last_parsed_at = now
                chat.parse_count = (chat.parse_count or 0) + 1
                chat.extra_data = {**(chat.extra_data or {}), **metadata}
            saved.append(chat)

        await self.session.commit()
        for chat in saved:
            await self.session.refresh(chat)
        return saved

    async def _account(
        self,
        owner_id: UUID,
        platform: str,
        account_id: UUID | None,
    ) -> Account | None:
        stmt = select(Account).where(
            Account.owner_id == owner_id,
            Account.platform == platform,
            Account.is_active.is_(True),
            Account.status == "active",
        )
        if account_id is not None:
            stmt = stmt.where(Account.id == account_id)
        result = await self.session.execute(
            stmt.order_by(Account.health_score.desc(), Account.last_used_at.asc().nullsfirst()).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _numeric_chat_id(platform: str, external_id: str) -> int:
        try:
            value = int(external_id)
        except ValueError as exc:
            raise ValueError(
                f"Connector {platform} returned a non-numeric community id; "
                "canonical string community ids are not migrated yet"
            ) from exc
        # Telegram legacy IDs use a negative namespace. Other numeric platforms
        # retain their native ID so existing IntelligenceService can pass it back
        # into the connector without another lookup layer.
        if platform == "telegram":
            return -abs(value)
        return value
