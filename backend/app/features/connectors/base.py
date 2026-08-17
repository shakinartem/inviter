from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ConnectorCapabilities:
    connect_account: bool = False
    discover_communities: bool = False
    read_community: bool = False
    read_messages: bool = False
    read_members: bool = False
    read_member_activity: bool = False
    direct_invite: bool = False
    invite_link: bool = False
    direct_message: bool = False

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


class MessengerConnector(ABC):
    """Stable platform boundary used by discovery, audience and campaigns.

    Platform-specific SDK objects must not leak outside connector implementations.
    """

    platform: str
    display_name: str
    capabilities: ConnectorCapabilities

    def describe(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "capabilities": self.capabilities.as_dict(),
        }

    @abstractmethod
    async def check_account(self, account: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def discover_communities(
        self,
        query: str,
        *,
        account: Any | None = None,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_members(
        self,
        community: Any,
        *,
        account: Any,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def execute_action(
        self,
        action: str,
        *,
        account: Any,
        target: dict[str, Any],
        destination: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError
