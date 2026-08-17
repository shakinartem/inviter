from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.features.connectors.base import ConnectorCapabilities, MessengerConnector


DISCORD_API = "https://discord.com/api/v10"


class DiscordConnector(MessengerConnector):
    """Discord connector using only official Bot/OAuth2 API authentication.

    Standard Discord user tokens/self-bots are intentionally unsupported.
    Discovery means guilds the authorized bot/user is already allowed to see;
    Discord does not expose arbitrary global server-member scraping through this
    connector. Direct invite/unsolicited messaging actions are not advertised.
    """

    platform = "discord"
    display_name = "Discord"
    capabilities = ConnectorCapabilities(
        connect_account=True,
        discover_communities=True,
        read_community=True,
        read_messages=True,
        read_members=True,
        read_member_activity=True,
        direct_invite=False,
        invite_link=False,
        direct_message=False,
    )

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @staticmethod
    def _auth(account: Any) -> tuple[dict[str, str], str]:
        credentials = getattr(account, "credentials", {}) or {}
        auth_type = (getattr(account, "auth_type", "") or "").lower()

        if auth_type in {"bot", "bot_token"}:
            token = credentials.get("bot_token") or credentials.get("token")
            if not token:
                raise ValueError("Discord bot_token is required")
            return {"Authorization": f"Bot {token}"}, "bot_token"

        if auth_type in {"oauth2", "oauth2_access_token", "bearer"}:
            token = credentials.get("access_token")
            if not token:
                raise ValueError("Discord OAuth2 access_token is required")
            return {"Authorization": f"Bearer {token}"}, "oauth2"

        raise ValueError("Discord auth_type must be bot_token or oauth2")

    async def _request(
        self,
        account: Any,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        headers, _ = self._auth(account)
        headers["User-Agent"] = "Qualive-Intent-Intelligence/1.0"
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            response = await client.request(method, f"{DISCORD_API}{path}", params=params)
        if response.status_code == 204:
            return None
        if response.status_code >= 400:
            detail = response.text[:500]
            raise ValueError(f"Discord API {response.status_code}: {detail}")
        return response.json()

    async def check_account(self, account: Any) -> dict[str, Any]:
        user = await self._request(account, "GET", "/users/@me")
        _, auth_mode = self._auth(account)

        # OAuth2 user grants can enumerate their guilds with the guilds scope, but
        # broad member/message access is not assumed. Bot access can read members
        # and messages only where intents/permissions allow it at runtime.
        capabilities = self.capabilities.as_dict()
        if auth_mode == "oauth2":
            capabilities["read_messages"] = False
            capabilities["read_members"] = False
            capabilities["read_member_activity"] = False

        return {
            "ok": True,
            "external_account_id": str(user["id"]),
            "username": user.get("username"),
            "first_name": user.get("global_name") or user.get("username"),
            "last_name": None,
            "is_bot": bool(user.get("bot", False)),
            "capabilities": capabilities,
        }

    async def discover_communities(
        self,
        query: str,
        *,
        account: Any | None = None,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if account is None:
            raise ValueError("Discord discovery requires an authorized connection")

        guilds = await self._request(
            account,
            "GET",
            "/users/@me/guilds",
            params={"limit": min(max(limit, 1), 200), "with_counts": "true"},
        )
        needle = query.strip().lower()
        result: list[dict[str, Any]] = []
        for guild in guilds or []:
            name = str(guild.get("name") or "")
            if needle and needle not in name.lower():
                continue
            result.append(
                {
                    "platform": self.platform,
                    "external_id": str(guild["id"]),
                    "username": None,
                    "title": name,
                    "type": "guild",
                    "participants_count": guild.get("approximate_member_count"),
                    "active_participants": guild.get("approximate_presence_count"),
                    "raw": {
                        "features": guild.get("features") or [],
                        "permissions": guild.get("permissions"),
                        "owner": guild.get("owner"),
                    },
                }
            )
        return result[:limit]

    async def get_members(
        self,
        community: Any,
        *,
        account: Any,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        _, auth_mode = self._auth(account)
        if auth_mode != "bot_token":
            raise ValueError("Discord member enumeration requires a bot connection with GUILD_MEMBERS intent")

        wanted = max(limit or 1000, 1)
        guild_id = str(community)
        members: list[dict[str, Any]] = []
        after = "0"
        while len(members) < wanted:
            page_size = min(1000, wanted - len(members))
            page = await self._request(
                account,
                "GET",
                f"/guilds/{guild_id}/members",
                params={"limit": page_size, "after": after},
            )
            if not page:
                break
            for item in page:
                user = item.get("user") or {}
                user_id = user.get("id")
                if not user_id:
                    continue
                members.append(
                    {
                        "platform": self.platform,
                        "external_user_id": str(user_id),
                        "username": user.get("username"),
                        "first_name": user.get("global_name") or user.get("username"),
                        "last_name": None,
                        "is_bot": bool(user.get("bot", False)),
                        "is_verified": False,
                        "is_scam": False,
                        "is_fake": False,
                        "last_seen": None,
                        "raw": {
                            "nick": item.get("nick"),
                            "roles": item.get("roles") or [],
                            "joined_at": item.get("joined_at"),
                            "pending": item.get("pending", False),
                        },
                    }
                )
            after = str((page[-1].get("user") or {}).get("id") or "0")
            if len(page) < page_size or after == "0":
                break
        return members[:wanted]

    async def get_recent_messages(
        self,
        community: Any,
        *,
        account: Any,
        since: datetime,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        _, auth_mode = self._auth(account)
        if auth_mode != "bot_token":
            raise ValueError("Discord message reading requires a bot connection with channel permissions")
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        guild_id = str(community)
        channels = await self._request(account, "GET", f"/guilds/{guild_id}/channels")
        # Text (0), announcement (5), thread-like public channels (10/11/12/15)
        readable_types = {0, 5, 10, 11, 12, 15}
        channels = [channel for channel in channels or [] if channel.get("type") in readable_types]
        wanted = max(limit or 1000, 1)
        messages: list[dict[str, Any]] = []

        for channel in channels:
            if len(messages) >= wanted:
                break
            channel_id = str(channel["id"])
            before: str | None = None
            while len(messages) < wanted:
                params: dict[str, Any] = {"limit": min(100, wanted - len(messages))}
                if before:
                    params["before"] = before
                try:
                    page = await self._request(
                        account,
                        "GET",
                        f"/channels/{channel_id}/messages",
                        params=params,
                    )
                except ValueError as exc:
                    # A bot may see the guild but not this channel/history. Skip the
                    # channel rather than failing the whole community enrichment.
                    if "Discord API 403" in str(exc) or "Discord API 404" in str(exc):
                        break
                    raise
                if not page:
                    break

                oldest_seen: datetime | None = None
                for item in page:
                    timestamp_raw = item.get("timestamp")
                    if not timestamp_raw:
                        continue
                    created_at = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
                    oldest_seen = created_at if oldest_seen is None or created_at < oldest_seen else oldest_seen
                    if created_at < since:
                        continue
                    author = item.get("author") or {}
                    messages.append(
                        {
                            "platform": self.platform,
                            "external_message_id": str(item["id"]),
                            "external_user_id": str(author["id"]) if author.get("id") else None,
                            "created_at": created_at,
                            "text": item.get("content") or "",
                            "is_reply": (item.get("message_reference") or {}).get("message_id") is not None,
                            "views": None,
                            "forwards": None,
                            "channel_id": channel_id,
                        }
                    )
                    if len(messages) >= wanted:
                        break

                if oldest_seen is not None and oldest_seen < since:
                    break
                before = str(page[-1]["id"])
                if len(page) < params["limit"]:
                    break

        messages.sort(key=lambda item: item["created_at"], reverse=True)
        return messages[:wanted]

    async def execute_action(
        self,
        action: str,
        *,
        account: Any,
        target: dict[str, Any],
        destination: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "action": action,
            "code": "ACTION_NOT_SUPPORTED",
            "retryable": False,
            "message": "Discord connector does not automate direct member invites or unsolicited DMs",
        }
