from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel, Chat

from app.features.accounts.client_manager import TelegramClientManager
from app.features.connectors.base import ConnectorCapabilities, MessengerConnector


class TelegramConnector(MessengerConnector):
    platform = "telegram"
    display_name = "Telegram"
    capabilities = ConnectorCapabilities(
        connect_account=True,
        discover_communities=True,
        read_community=True,
        read_messages=True,
        read_members=True,
        read_member_activity=True,
        direct_invite=True,
        invite_link=True,
        direct_message=True,
    )

    def __init__(self, client_manager: TelegramClientManager | None = None) -> None:
        self.client_manager = client_manager or TelegramClientManager()

    async def check_account(self, account: Any) -> dict[str, Any]:
        client = await self.client_manager.get_client(account)
        try:
            me = await client.get_me()
            return {
                "ok": True,
                "external_account_id": str(me.id),
                "username": getattr(me, "username", None),
                "first_name": getattr(me, "first_name", None),
            }
        finally:
            await self.client_manager.release_client(account.id)

    async def discover_communities(
        self,
        query: str,
        *,
        account: Any | None = None,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if account is None:
            raise ValueError("Telegram discovery requires an authorized account")

        client = await self.client_manager.get_client(account)
        try:
            result = await client(SearchRequest(q=query, limit=min(max(limit, 1), 200)))
            communities: list[dict[str, Any]] = []
            for chat in result.chats:
                if not isinstance(chat, (Channel, Chat)):
                    continue
                chat_type = "group"
                if getattr(chat, "broadcast", False):
                    chat_type = "channel"
                elif getattr(chat, "megagroup", False):
                    chat_type = "supergroup"

                if filters and filters.get("chat_type") and filters["chat_type"] != chat_type:
                    continue

                communities.append(
                    {
                        "platform": self.platform,
                        "external_id": str(chat.id),
                        "username": getattr(chat, "username", None),
                        "title": getattr(chat, "title", None),
                        "type": chat_type,
                        "participants_count": getattr(chat, "participants_count", None),
                        "access_hash": (
                            str(getattr(chat, "access_hash"))
                            if getattr(chat, "access_hash", None) is not None
                            else None
                        ),
                        "raw": {
                            "verified": bool(getattr(chat, "verified", False)),
                            "scam": bool(getattr(chat, "scam", False)),
                            "fake": bool(getattr(chat, "fake", False)),
                        },
                    }
                )
            return communities
        finally:
            await self.client_manager.release_client(account.id)

    async def get_members(
        self,
        community: Any,
        *,
        account: Any,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        client = await self.client_manager.get_client(account)
        try:
            members: list[dict[str, Any]] = []
            async for user in client.iter_participants(community, limit=limit):
                status = getattr(user, "status", None)
                was_online = getattr(status, "was_online", None)
                members.append(
                    {
                        "platform": self.platform,
                        "external_user_id": str(user.id),
                        "username": getattr(user, "username", None),
                        "first_name": getattr(user, "first_name", None),
                        "last_name": getattr(user, "last_name", None),
                        "is_bot": bool(getattr(user, "bot", False)),
                        "is_verified": bool(getattr(user, "verified", False)),
                        "is_scam": bool(getattr(user, "scam", False)),
                        "is_fake": bool(getattr(user, "fake", False)),
                        "last_seen": was_online,
                    }
                )
            return members
        finally:
            await self.client_manager.release_client(account.id)

    async def get_recent_messages(
        self,
        community: Any,
        *,
        account: Any,
        since: datetime,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        client = await self.client_manager.get_client(account)
        try:
            messages: list[dict[str, Any]] = []
            async for message in client.iter_messages(community, limit=limit):
                created_at = getattr(message, "date", None)
                if created_at is None:
                    continue
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if created_at < since:
                    break

                sender_id = getattr(message, "sender_id", None)
                messages.append(
                    {
                        "platform": self.platform,
                        "external_message_id": str(message.id),
                        "external_user_id": str(sender_id) if sender_id is not None else None,
                        "created_at": created_at,
                        "text": getattr(message, "message", None) or "",
                        "is_reply": getattr(message, "reply_to_msg_id", None) is not None,
                        "views": getattr(message, "views", None),
                        "forwards": getattr(message, "forwards", None),
                    }
                )
            return messages
        finally:
            await self.client_manager.release_client(account.id)

    async def execute_action(
        self,
        action: str,
        *,
        account: Any,
        target: dict[str, Any],
        destination: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if action != "direct_invite":
            raise ValueError(f"Telegram action is not implemented yet: {action}")
        if not destination or destination.get("external_id") is None:
            raise ValueError("destination.external_id is required")
        if target.get("external_user_id") is None:
            raise ValueError("target.external_user_id is required")

        client = await self.client_manager.get_client(account)
        try:
            await client.invite_to_chat(
                int(destination["external_id"]),
                [int(target["external_user_id"])],
            )
            return {"ok": True, "action": action}
        finally:
            await self.client_manager.release_client(account.id)
