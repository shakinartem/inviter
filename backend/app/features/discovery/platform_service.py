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
    """Discover communities through any installed connector and persist them."""

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
        normalized_query = query.strip()
        source = "telegram_dialogs" if platform == "telegram" and not normalized_query else f"{platform}_connector"

        for community in communities:
            external_id = str(community.get("external_id") or "").strip()
            if not external_id:
                continue
            chat_id = self._numeric_chat_id(platform, external_id)
            username = community.get("username")
            access_hash = community.get("access_hash")
            community_type = community.get("type") or "community"

            metadata = dict(community.get("raw") or {})
            metadata.update(
                {
                    "platform": platform,
                    "external_id": external_id,
                    "discovery_query": normalized_query,
                    "discovery_mode": "dialogs" if source == "telegram_dialogs" else "search",
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
                    username=username,
                    title=community.get("title"),
                    description=community.get("description"),
                    access_hash=access_hash,
                    chat_type=community_type,
                    participants_count=community.get("participants_count"),
                    active_participants=community.get("active_participants"),
                    category=None,
                    niche=normalized_query or None,
                    tags=None,
                    language=None,
                    country=None,
                    is_public=bool(username),
                    is_active=True,
                    is_restricted=False,
                    source=source,
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
                chat.username = username or chat.username
                chat.access_hash = access_hash or chat.access_hash
                chat.chat_type = community_type or chat.chat_type
                participants = community.get("participants_count")
                if participants is not None:
                    chat.participants_count = participants
                active_participants = community.get("active_participants")
                if active_participants is not None:
                    chat.active_participants = active_participants
                if normalized_query:
                    chat.niche = normalized_query
                chat.is_public = bool(chat.username)
                chat.source = source
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
                f"Connector {platform} returned a non-numeric community id; canonical string community ids are not migrated yet"
            ) from exc
        if platform == "telegram":
            return -abs(value)
        return value
