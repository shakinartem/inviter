from __future__ import annotations

from typing import Optional
from uuid import UUID

from loguru import logger
from telethon import TelegramClient

from app.features.accounts.models import Account
from app.features.proxies.models import Proxy


class TelegramClientManager:
    """
    Manager for Telegram client sessions.
    Handles creating, caching, and releasing Telegram clients.
    """

    def __init__(self):
        self._clients: dict[UUID, TelegramClient] = {}

    async def get_client(self, account: Account, proxy: Optional[Proxy] = None) -> TelegramClient:
        """
        Get or create a Telegram client for the given account.
        """
        if account.id in self._clients:
            return self._clients[account.id]

        proxy_dict = None
        if proxy:
            proxy_dict = {
                "proxy_type": proxy.scheme,
                "addr": proxy.host,
                "port": proxy.port,
                "username": proxy.username,
                "password": proxy.password,
            } if any([proxy.host, proxy.port]) else None

        client = TelegramClient(
            session=f"sessions/{account.session_name}",
            api_id=account.api_id or 0,
            api_hash=account.api_hash or "",
            proxy=proxy_dict,
        )
        await client.connect()
        self._clients[account.id] = client
        logger.bind(account_id=account.id).info("Telegram client created")
        return client

    async def release_client(self, client: TelegramClient) -> None:
        """
        Release a Telegram client (no-op for now, keeps connection alive).
        """
        pass

    async def disconnect_all(self) -> None:
        """
        Disconnect all Telegram clients.
        """
        for account_id, client in self._clients.items():
            try:
                await client.disconnect()
                logger.bind(account_id=account_id).info("Telegram client disconnected")
            except Exception as e:
                logger.bind(account_id=account_id).error(f"Error disconnecting client: {e}")
        self._clients.clear()