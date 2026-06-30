"""Telegram client manager for the Inviter project.

Singleton manager that maintains a pool of Telethon ``TelegramClient``
instances, handles session file I/O, proxy configuration, automatic
error handling, Redis-based rate limiting / flood protection, and daily
invite counters.

Intended usage from ``AccountService``::

    cm = TelegramClientManager(redis=redis)
    client = await cm.get_client(account, proxy)
    ...
    await cm.release_client(account.id)
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from redis.asyncio import Redis
from telethon import TelegramClient
from telethon import errors as te

from app.core.config import settings

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
SESSION_DIR = Path(getattr(settings, "sessions_dir", "sessions"))
SESSION_DIR.mkdir(parents=True, exist_ok=True)

_DAILY_LIMIT_KEY = "account:daily_invites:{account_id}"
_FLOODWAIT_KEY = "account:floodwait:{account_id}"
_DAILY_RESET_KEY = "account:daily_reset:{account_id}"

logger = logging.getLogger("TelegramClientManager")


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class ClientError(Exception):
    """Базовая ошибка менеджера клиентов."""
    def __init__(self, message: str, account_id: UUID | None = None, reason: str = "unknown"):
        self.account_id = account_id
        self.reason = reason
        super().__init__(f"[{account_id}] {message} (reason={reason})")


class SessionInvalidError(ClientError):
    """Сессионный файл повреждён или имеет невалидную сигнатуру."""
    def __init__(self, account_id: UUID, session_path: str):
        super().__init__(f"Invalid session: {session_path}", account_id, "invalid_session")


class AuthenticationError(ClientError):
    """Auth key невалиден, сессия истекла или аккаунт заблокирован."""
    def __init__(self, account_id: UUID, reason: str = "auth_failed"):
        super().__init__("Authentication failed", account_id, reason)


class FloodLimitError(ClientError):
    """FloodWait / PeerFlood — аккаунту нужен отдых."""
    def __init__(self, account_id: UUID, wait_seconds: int = 0, reason: str = "flood"):
        self.wait_seconds = wait_seconds
        super().__init__(
            f"Flood limit, wait {wait_seconds}s" if wait_seconds else "Flood limit",
            account_id,
            reason,
        )


# --------------------------------------------------------------------------- #
# Singleton
# --------------------------------------------------------------------------- #
class TelegramClientManager:
    """Singleton-менеджер Telethon-клиентов.

    • Пул клиентов в памяти ``_clients: dict[UUID, TelegramClient]``
    • Проверка SQLite-сигнатуры ``.session``-файлов
    • Автоматическая обработка ключевых ошибок Telethon
    • Redis-based rate limiting, flood wait, дневные счётчики
    • Автообновление статуса аккаунта в БД при ошибках

    Использование (из ``AccountService``)::

        cm = TelegramClientManager(redis=redis)
        client = await cm.get_client(account, proxy)
        ...
        await cm.release_client(account.id)
    """

    _instance: Optional[TelegramClientManager] = None

    def __new__(cls, **kwargs: Any) -> TelegramClientManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, redis: Optional[Redis] = None) -> None:
        if getattr(self, "_inited", False):
            # Позволяем обновить redis-ссылку
            if redis is not None:
                self._redis = redis
            return

        # ---- client pool ----
        self._clients: Dict[UUID, TelegramClient] = {}
        self._locks: Dict[UUID, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        # ---- redis ----
        self._redis: Optional[Redis] = redis

        # ---- metadata ----
        self._fingerprints: Dict[UUID, str] = {}
        self._last_error: Dict[UUID, Tuple[str, datetime]] = {}
        self._connection_attempts: Dict[UUID, int] = {}

        self._inited = True
        logger.info("TelegramClientManager initialized")

    # ===================================================================== #
    # Session file helpers
    # ===================================================================== #
    @staticmethod
    def _session_path(session_name: str) -> Path:
        """Путь к ``.session``-файлу по имени сессии."""
        return SESSION_DIR / f"{session_name}.session"

    def session_exists(self, session_name: str) -> bool:
        """Проверить существование ``.session``-файла."""
        return self._session_path(session_name).is_file()

    def get_session_file_size(self, session_name: str) -> int:
        """Размер ``.session``-файла в байтах (0 если не найден)."""
        p = self._session_path(session_name)
        return p.stat().st_size if p.is_file() else 0

    def save_session_bytes(self, session_name: str, data: bytes) -> Path:
        """Сохранить байты ``.session``-файла на диск."""
        path = self._session_path(session_name)
        path.write_bytes(data)
        logger.info("Session file saved", path=str(path), size=len(data))
        return path

    def delete_session_file(self, session_name: str) -> bool:
        """Удалить ``.session``-файл. Возвращает True если удалён."""
        path = self._session_path(session_name)
        if path.is_file():
            path.unlink()
            logger.info("Session file deleted", path=str(path))
            return True
        return False

    @staticmethod
    def _validate_session_sqlite(path: Path | str) -> bool:
        """Проверить сигнатуру SQLite3 в первых 16 байтах."""
        try:
            with open(path, "rb") as f:
                header = f.read(16)
            return header[:16] == b"SQLite format 3\x00"
        except (OSError, IOError):
            return False

    # ===================================================================== #
    # Redis helpers
    # ===================================================================== #
    async def _check_rate_limit(self, account_id: UUID) -> None:
        """Raise FloodLimitError если аккаунт превысил лимит инвайтов/мин."""
        if self._redis is None:
            return
        key = f"inviter:rate_limit:{account_id}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 60)
        max_per_minute = getattr(settings, "account_rate_limit_per_minute", 20)
        if count > max_per_minute:
            raise FloodLimitError(account_id, wait_seconds=60, reason="rate_limit")

    # ---- FloodWait (Redis) ----
    async def set_floodwait(self, account_id: UUID, seconds: int) -> None:
        """Установить flood-wait в Redis."""
        if self._redis is None:
            return
        key = _FLOODWAIT_KEY.format(account_id=account_id)
        deadline = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        await self._redis.set(key, str(int(deadline.timestamp())), ex=min(seconds + 60, 86400 * 3))
        logger.warning("FloodWait set", account_id=str(account_id), seconds=seconds)

    async def get_floodwait_remaining(self, account_id: UUID) -> int:
        """Сколько секунд осталось flood-wait. 0 = нет активного."""
        if self._redis is None:
            return 0
        key = _FLOODWAIT_KEY.format(account_id=account_id)
        raw = await self._redis.get(key)
        if not raw:
            return 0
        try:
            deadline_ts = int(raw)
        except (ValueError, TypeError):
            return 0
        now_ts = int(datetime.now(timezone.utc).timestamp())
        remaining = deadline_ts - now_ts
        return max(remaining, 0)

    async def clear_floodwait(self, account_id: UUID) -> None:
        if self._redis is None:
            return
        key = _FLOODWAIT_KEY.format(account_id=account_id)
        await self._redis.delete(key)

    # ---- Daily invite counter (Redis) ----
    async def increment_daily_invites(self, account_id: UUID) -> int:
        """Инкремент дневного счётчика инвайтов. Возвращает новое значение."""
        if self._redis is None:
            return 0
        key = _DAILY_LIMIT_KEY.format(account_id=account_id)
        val = await self._redis.incr(key)
        if val == 1:
            # TTL до следующего UTC 00:00 + запас
            now = datetime.now(timezone.utc)
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            ttl = int((tomorrow - now).total_seconds()) + 60
            await self._redis.expire(key, ttl)
        return val

    async def get_daily_invites(self, account_id: UUID) -> int:
        """Текущее значение дневного счётчика."""
        if self._redis is None:
            return 0
        key = _DAILY_LIMIT_KEY.format(account_id=account_id)
        raw = await self._redis.get(key)
        return int(raw) if raw else 0

    async def reset_daily_invites(self, account_id: UUID) -> None:
        """Сбросить дневной счётчик."""
        if self._redis is None:
            return
        key = _DAILY_LIMIT_KEY.format(account_id=account_id)
        await self._redis.delete(key)

    # ===================================================================== #
    # Proxy builder
    # ===================================================================== #
    @staticmethod
    def _build_proxy(proxy: Any) -> Optional[Dict[str, Any]]:
        """Преобразовать ``Proxy``-модель в dict-параметры для Telethon.

        Поддержка: SOCKS5, HTTP, MTProto.
        """
        if proxy is None:
            return None

        scheme = (getattr(proxy, "scheme", None) or "socks5").lower()
        host = proxy.host
        port = proxy.port

        if scheme == "mtproto":
            return {
                "proxy_type": "mtproto",
                "dc_id": 1,
                "server": host,
                "port": port,
                "secret": getattr(proxy, "password", "") or "",
            }

        result: Dict[str, Any] = {
            "proxy_type": scheme,
            "addr": host,
            "port": port,
            "rdns": True,
        }
        if getattr(proxy, "username", None):
            result["username"] = proxy.username
        if getattr(proxy, "password", None):
            result["password"] = proxy.password
        return result

    # ===================================================================== #
    # Core public API
    # ===================================================================== #
    async def get_client(
        self,
        account: Any,
        proxy: Any = None,
        force_new: bool = False,
    ) -> TelegramClient:
        """Получить Telethon-клиент для аккаунта.

        Если клиент уже в пуле и подключён — возвращается из кэша.
        Иначе создаётся новый с учётом прокси и ``.session``-файла.

        Parameters
        ----------
        account : Account
            ORM-модель аккаунта (обязательно ``session_name``, ``api_id``, ``api_hash``).
        proxy : Proxy | None
            ORM-модель прокси.
        force_new : bool
            Если True — создать клиент заново (игнорировать кэш).
        """
        account_id: UUID = account.id
        fp = self._fingerprint(account)

        # Проверяем flood wait
        fw = await self.get_floodwait_remaining(account_id)
        if fw > 0:
            raise FloodLimitError(account_id, wait_seconds=fw, reason="flood_wait")

        # Проверяем кэш
        if not force_new and account_id in self._clients:
            client = self._clients[account_id]
            if client.is_connected():
                return client
            # stale
            self._clients.pop(account_id, None)

        # ---- Создание нового клиента ----
        session_path = self._session_path(account.session_name)

        if not session_path.is_file():
            logger.error("Session file missing", fp=fp, path=str(session_path))
            raise SessionInvalidError(account_id, str(session_path))

        if not self._validate_session_sqlite(session_path):
            logger.error("Session file invalid (bad SQLite signature)", fp=fp)
            raise SessionInvalidError(account_id, str(session_path))

        proxy_dict = self._build_proxy(proxy)

        client = TelegramClient(
            session=str(session_path),
            api_id=account.api_id,
            api_hash=account.api_hash,
            proxy=proxy_dict,
            connection_retries=3,
            timeout=30,
            request_retries=3,
            auto_reconnect=False,
        )

        try:
            await client.start()
        except te.AuthKeyUnregisteredError:
            logger.error("AuthKey unregistered", fp=fp)
            await self._update_account_status(account, "banned", "AuthKeyUnregistered — re-upload session")
            raise AuthenticationError(account_id, "auth_key_unregistered")

        except te.UserDeactivatedError:
            logger.error("Account deactivated", fp=fp)
            await self._update_account_status(account, "banned", "Account deactivated by Telegram")
            raise AuthenticationError(account_id, "user_deactivated")

        except te.UserDeactivatedBanError:
            logger.error("Account banned", fp=fp)
            await self._update_account_status(account, "banned", "Account banned by Telegram")
            raise AuthenticationError(account_id, "user_deactivated_ban")

        except te.SessionPasswordNeededError:
            logger.error("2FA required (SessionPasswordNeeded)", fp=fp)
            await self._update_account_status(account, "error", "2FA password needed")
            raise AuthenticationError(account_id, "session_password_needed")

        except te.PasswordHashInvalidError:
            logger.error("Invalid 2FA password", fp=fp)
            await self._update_account_status(account, "error", "Invalid 2FA password")
            raise AuthenticationError(account_id, "password_hash_invalid")

        except te.PhoneMigrateError as exc:
            logger.warning("PhoneMigrate to DC%s", exc.new_dc, fp=fp)
            raise ClientError(f"Phone migration to DC{exc.new_dc}", account_id, "phone_migrate")

        except te.FloodWaitError as exc:
            wait = exc.seconds
            logger.warning("FloodWait %ds", wait, fp=fp)
            await self.set_floodwait(account_id, wait)
            await self._update_account_status(account, "cooldown", f"FloodWait {wait}s")
            raise FloodLimitError(account_id, wait_seconds=wait, reason="flood_wait")

        except te.PeerFloodError:
            logger.warning("PeerFloodError", fp=fp)
            await self.set_floodwait(account_id, 3600)
            await self._update_account_status(account, "limited", "PeerFlood — hourly cooldown")
            raise FloodLimitError(account_id, wait_seconds=3600, reason="peer_flood")

        except Exception as exc:
            logger.exception("Unexpected error creating client", fp=fp)
            await self._update_account_status(account, "error", str(exc)[:500])
            raise

        self._clients[account_id] = client
        self._connection_attempts[account_id] = 0
        self._fingerprints[account_id] = fp

        # Успешно — сбрасываем статус ошибки / cooldown
        await self._update_account_status(account, "active", None)
        await self.clear_floodwait(account_id)

        logger.info("Client created", fp=fp)
        return client

    async def disconnect_client(self, account_id: UUID) -> None:
        """Gracefully отключить и удалить клиент из пула."""
        client = self._clients.pop(account_id, None)
        self._locks.pop(account_id, None)
        if client is not None:
            try:
                if client.is_connected():
                    await client.disconnect()
            except Exception:
                pass
        fp = self._fingerprints.pop(account_id, "?")
        logger.debug("Client disconnected", account_id=str(account_id), fp=fp)

    async def invalidate_client(self, account_id: UUID) -> None:
        """Отключить клиент (игнорируя ошибки)."""
        await self.disconnect_client(account_id)

    async def bulk_invalidate(self, account_ids: List[UUID]) -> None:
        """Массовая инвалидация клиентов."""
        for aid in account_ids:
            await self.invalidate_client(aid)
        logger.info("Bulk invalidate", count=len(account_ids))

    async def release_client(self, account_id: UUID) -> None:
        """Освободить клиент (для InviterService)."""
        await self.disconnect_client(account_id)

    # ===================================================================== #
    # check_account — проверка авторизации
    # ===================================================================== #
    async def check_account(self, account: Any) -> dict:
        """Проверить авторизацию аккаунта через Telegram API.

        Возвращает dict с данными профиля и статусом.
        """
        proxy = None
        if getattr(account, "proxy_id", None):
            proxy = getattr(account, "proxy", None)

        try:
            client = await self.get_client(account, proxy)
        except (AuthenticationError, FloodLimitError, SessionInvalidError, ClientError) as exc:
            return {
                "is_authorized": False,
                "status": "error",
                "status_message": str(exc),
            }

        try:
            me = await client.get_me()
        except te.AuthKeyUnregisteredError:
            return {
                "is_authorized": False,
                "status": "banned",
                "status_message": "AuthKey unregistered",
            }
        except te.UserDeactivatedError:
            return {
                "is_authorized": False,
                "status": "banned",
                "status_message": "Account deactivated",
            }
        except te.UserDeactivatedBanError:
            return {
                "is_authorized": False,
                "status": "banned",
                "status_message": "Account banned",
            }
        except te.FloodWaitError as exc:
            await self.set_floodwait(account.id, exc.seconds)
            return {
                "is_authorized": False,
                "status": "cooldown",
                "status_message": f"FloodWait {exc.seconds}s",
            }
        except te.PeerFloodError:
            await self.set_floodwait(account.id, 3600)
            return {
                "is_authorized": False,
                "status": "limited",
                "status_message": "PeerFlood",
            }
        except Exception as exc:
            return {
                "is_authorized": False,
                "status": "error",
                "status_message": str(exc)[:500],
            }
        finally:
            await self.disconnect_client(account.id)

        return {
            "is_authorized": True,
            "status": "active",
            "status_message": None,
            "telegram_user_id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "phone": getattr(me, "phone", None),
            "is_premium": bool(
                getattr(me, "premium", False)
                or getattr(me, "is_premium", False)
            ),
            "is_bot": me.bot if hasattr(me, "bot") else False,
        }

    # ===================================================================== #
    # Pool management
    # ===================================================================== #
    async def cleanup_disconnected(self) -> int:
        """Удалить отключённые клиенты из пула. Возвращает количество."""
        removed = 0
        async with self._global_lock:
            stale = [aid for aid, c in self._clients.items() if not c.is_connected()]
            for aid in stale:
                self._clients.pop(aid, None)
                self._locks.pop(aid, None)
                removed += 1
        if removed:
            logger.info("Cleaned up stale clients", count=removed)
        return removed

    async def get_health_stats(self) -> Dict[str, Any]:
        """Статистика пула клиентов."""
        async with self._global_lock:
            total = len(self._clients)
            connected = sum(1 for c in self._clients.values() if c.is_connected())
            flood_waits = 0
            if self._redis:
                for aid in list(self._clients.keys()):
                    if await self.get_floodwait_remaining(aid) > 0:
                        flood_waits += 1
            return {
                "total_clients": total,
                "connected_clients": connected,
                "disconnected_clients": total - connected,
                "flood_wait_clients": flood_waits,
            }

    async def get_client_status(self, account_id: UUID) -> Dict[str, Any]:
        """Детальный статус одного клиента."""
        client = self._clients.get(account_id)
        fw = await self.get_floodwait_remaining(account_id)
        last_err = self._last_error.get(account_id)
        return {
            "account_id": str(account_id),
            "in_pool": client is not None,
            "connected": client.is_connected() if client else False,
            "flood_wait_remaining": fw,
            "last_error": last_err[0] if last_err else None,
            "last_error_at": last_err[1].isoformat() if last_err else None,
            "attempts": self._connection_attempts.get(account_id, 0),
        }

    # ===================================================================== #
    # Per-account locking
    # ===================================================================== #
    def _get_lock(self, account_id: UUID) -> asyncio.Lock:
        if account_id not in self._locks:
            self._locks[account_id] = asyncio.Lock()
        return self._locks[account_id]

    # ===================================================================== #
    # Private helpers
    # ===================================================================== #
    def _fingerprint(self, account: Any) -> str:
        """Короткий отпечаток для логов (без утечки данных)."""
        if hasattr(account, "fingerprint"):
            return account.fingerprint
        phone = getattr(account, "phone", "") or ""
        api_id = getattr(account, "api_id", "") or ""
        session = getattr(account, "session_name", "") or ""
        import hashlib
        return hashlib.sha1(f"{phone}|{api_id}|{session}".encode()).hexdigest()[:8]

    async def _update_account_status(
        self,
        account: Any,
        status: str,
        message: Optional[str],
    ) -> None:
        """Обновить статус аккаунта в БД."""
        fp = self._fingerprints.get(account.id, self._fingerprint(account))
        logger.info(
            "Account status update",
            account_id=str(account.id),
            fp=fp,
            new_status=status,
            message=message,
        )
        try:
            account.status = status
            if message is not None:
                account.status_message = message
            if status == "active":
                account.banned_until = None
                account.cooldown_until = None
            elif status == "cooldown":
                # Если нужен FloodWait — установим cooldown_until
                pass
            elif status == "banned":
                from datetime import timezone as _tz
                account.banned_until = datetime.now(_tz.utc) + timedelta(hours=24)
            account.last_checked_at = datetime.now(timezone.utc)
            # Если у account есть session (SQLAlchemy) — коммитим
            if hasattr(account, "__sa_instance_state__"):
                session = account.__sa_instance_state__.session
                if session is not None:
                    await session.commit()
        except Exception as exc:
            logger.error("Failed to update account status", account_id=str(account.id), error=str(exc))

    # ===================================================================== #
    # Shutdown
    # ===================================================================== #
    async def close(self) -> None:
        """Отключить все клиенты и освободить ресурсы."""
        async with self._global_lock:
            for account_id in list(self._clients.keys()):
                try:
                    c = self._clients[account_id]
                    if c.is_connected():
                        await c.disconnect()
                except Exception:
                    pass
            self._clients.clear()
            self._locks.clear()
            self._fingerprints.clear()
        logger.info("TelegramClientManager shut down")

    # ===================================================================== #
    # Async context manager
    # ===================================================================== #
    async def __aenter__(self) -> TelegramClientManager:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()


# --------------------------------------------------------------------------- #
# Global singleton (importable)
# --------------------------------------------------------------------------- #
manager = TelegramClientManager()
