"""
Сервис управления прокси-серверами.

Предоставляет:
- CRUD операции с прокси
- Проверка работоспособности (ping + connect test)
- Массовое создание / тестирование
- Кэширование рабочих прокси в Redis
- Защита от удаления прокси, используемых активными аккаунтами
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import Select, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.accounts.models import Account
from app.features.proxies.models import PROXY_TYPES, Proxy
from app.features.proxies.schemas import (
    BulkProxyCreate,
    ProxyCreate,
    ProxyListFilter,
    ProxyStats,
    ProxyTestResult,
    ProxyUpdate,
    ProxyTextImport,
)

# ==================== Constants ====================

WORKING_PROXIES_CACHE_KEY = "proxies:working"
WORKING_PROXIES_CACHE_TTL = 300  # 5 минут
PROXY_TEST_TIMEOUT = 10  # секунд на тест одного прокси

_LOGGER = logger.bind(module="ProxyService")


# ==================== Service ====================


class ProxyService:
    """Сервис для управления прокси-серверами."""

    def __init__(self, session: AsyncSession, redis: Optional[Redis] = None):
        self.session = session
        self._redis = redis

    # ================================================================== #
    #   CREATE
    # ================================================================== #

    async def create_proxy(self, data: ProxyCreate, owner_id: UUID) -> Proxy:
        """Создать новый прокси."""
        proxy = Proxy(
            owner_id=owner_id,
            title=data.title,
            scheme=data.scheme,
            host=data.host,
            port=data.port,
            username=data.username,
            password=data.password,
            secret=data.secret,
            country=data.country,
            city=data.city,
            notes=data.notes,
            extra_data=data.extra_data,
        )
        self.session.add(proxy)
        await self.session.commit()
        await self.session.refresh(proxy)

        log = _LOGGER.bind(proxy_id=str(proxy.id), fp=proxy.display_name)
        log.info("Proxy created", scheme=proxy.scheme, host=proxy.host, port=proxy.port)

        # После создания сразу запускаем проверку (но не блокируем ответ)
        asyncio.create_task(self._auto_test_after_create(proxy))

        return proxy

    async def bulk_create(self, data: BulkProxyCreate, owner_id: UUID) -> list[Proxy]:
        """Массовое создание прокси."""
        proxies: list[Proxy] = []
        for proxy_data in data.proxies:
            proxy = Proxy(
                owner_id=owner_id,
                title=proxy_data.title,
                scheme=proxy_data.scheme,
                host=proxy_data.host,
                port=proxy_data.port,
                username=proxy_data.username,
                password=proxy_data.password,
                secret=proxy_data.secret,
                country=proxy_data.country,
                city=proxy_data.city,
                notes=proxy_data.notes,
                extra_data=proxy_data.extra_data,
            )
            self.session.add(proxy)
            proxies.append(proxy)

        await self.session.commit()

        log = _LOGGER.bind(count=len(proxies))
        log.info("Bulk proxies created")

        # Запускаем фоновую проверку для всех новых прокси
        for proxy in proxies:
            asyncio.create_task(self._auto_test_after_create(proxy))

        return proxies

    async def import_from_text(
        self, data: ProxyTextImport, owner_id: UUID
    ) -> list[Proxy]:
        """Импорт прокси из текстового формата (построчно)."""
        lines = data.text.strip().split("\n")
        proxies: list[Proxy] = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                proxy = await self._parse_proxy_line(line, data.default_scheme, owner_id)
                if proxy:
                    self.session.add(proxy)
                    proxies.append(proxy)
            except ValueError as exc:
                _LOGGER.warning("Skipping invalid proxy line", line=line, error=str(exc))

        await self.session.commit()

        if proxies:
            _LOGGER.info(
                "Proxies imported from text",
                total=len(proxies),
                skipped=len(lines) - len(proxies),
            )

        return proxies

    async def _parse_proxy_line(
        self, line: str, default_scheme: str, owner_id: UUID
    ) -> Optional[Proxy]:
        """Распарсить одну строку с прокси в модель Proxy."""
        # Формат: scheme://user:password@host:port
        # или: scheme://host:port
        # или: host:port
        line = line.strip()
        if not line:
            return None

        scheme = default_scheme
        username = None
        password = None
        host: Optional[str] = None
        port: Optional[int] = None

        # Пробуем распарсить URL-формат
        url_match = re.match(
            r"^(?:(https?|socks5|mtproto)://)?"
            r"(?:([^:@]+):([^@]*)@)?"
            r"([a-zA-Z0-9.-]+|\[?[a-fA-F0-9:]+\]?)"
            r":(\d+)$",
            line,
        )

        if url_match:
            if url_match.group(1):
                scheme = url_match.group(1)
            username = url_match.group(2)
            password = url_match.group(3)
            host = url_match.group(4)
            port = int(url_match.group(5))
        else:
            # Пробуем формат host:port
            simple_match = re.match(r"^([a-zA-Z0-9.-]+):(\d+)$", line)
            if simple_match:
                host = simple_match.group(1)
                port = int(simple_match.group(2))
            else:
                raise ValueError(f"Cannot parse proxy line: {line}")

        if scheme not in PROXY_TYPES:
            scheme = default_scheme

        title = f"{scheme}://{host}:{port}"

        return Proxy(
            owner_id=owner_id,
            title=title,
            scheme=scheme,
            host=host,
            port=port,
            username=username,
            password=password,
        )

    async def _auto_test_after_create(self, proxy: Proxy) -> None:
        """Фоновая проверка прокси сразу после создания."""
        try:
            result = await self._test_proxy_connection(
                host=proxy.host,
                port=proxy.port,
                scheme=proxy.scheme,
                username=proxy.username,
                password=proxy.password,
                secret=proxy.secret,
            )
            await self._update_test_result(proxy, result)
            log = _LOGGER.bind(proxy_id=str(proxy.id))
            log.info(
                "Auto-test after create",
                working=result.is_working,
                ping_ms=result.ping_ms,
            )
        except Exception as exc:
            log = _LOGGER.bind(proxy_id=str(proxy.id))
            log.error("Auto-test failed", error=str(exc))

    # ================================================================== #
    #   READ
    # ================================================================== #

    async def get_proxy(self, proxy_id: UUID, owner_id: UUID) -> Optional[Proxy]:
        """Получить прокси по ID (с проверкой владельца)."""
        result = await self.session.execute(
            select(Proxy)
            .options(selectinload(Proxy.accounts))
            .where(Proxy.id == proxy_id, Proxy.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def get_proxy_by_id(self, proxy_id: UUID) -> Optional[Proxy]:
        """Получить прокси по ID без проверки владельца (для внутренних нужд)."""
        result = await self.session.execute(
            select(Proxy)
            .options(selectinload(Proxy.accounts))
            .where(Proxy.id == proxy_id)
        )
        return result.scalar_one_or_none()

    async def list_proxies(
        self,
        owner_id: UUID,
        filters: Optional[ProxyListFilter] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Proxy], int]:
        """Получить список прокси с фильтрацией и пагинацией."""
        query = (
            select(Proxy)
            .options(selectinload(Proxy.accounts))
            .where(Proxy.owner_id == owner_id)
        )

        if filters:
            query = self._apply_filters(query, filters)

        # По умолчанию — сначала новые
        query = query.order_by(Proxy.created_at.desc())

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Pagination
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        proxies = list(result.scalars().all())

        return proxies, total

    def _apply_filters(self, query: Select, filters: ProxyListFilter) -> Select:
        """Применить фильтры к запросу."""
        if filters.scheme is not None:
            query = query.where(Proxy.scheme == filters.scheme)
        if filters.is_active is not None:
            query = query.where(Proxy.is_active == filters.is_active)
        if filters.is_working is not None:
            query = query.where(Proxy.is_working == filters.is_working)
        if filters.country is not None:
            query = query.where(Proxy.country == filters.country)
        if filters.search:
            search_pattern = f"%{filters.search}%"
            query = query.where(
                or_(
                    Proxy.title.ilike(search_pattern),
                    Proxy.host.ilike(search_pattern),
                )
            )
        if filters.created_after is not None:
            query = query.where(Proxy.created_at >= filters.created_after)
        if filters.created_before is not None:
            query = query.where(Proxy.created_at <= filters.created_before)

        return query

    async def get_working_proxies(
        self, owner_id: Optional[UUID] = None
    ) -> list[Proxy]:
        """Получить список рабочих прокси (с Redis-кэшем)."""
        # Пробуем из кэша
        if self._redis and owner_id:
            cached = await self._get_cached_working_ids(owner_id)
            if cached is not None:
                result = await self.session.execute(
                    select(Proxy).where(
                        Proxy.id.in_(cached),
                        Proxy.owner_id == owner_id,
                    )
                )
                return list(result.scalars().all())

        # Из БД
        query = select(Proxy).options(selectinload(Proxy.accounts)).where(
            Proxy.is_active.is_(True),
            Proxy.is_working.is_(True),
        )
        if owner_id:
            query = query.where(Proxy.owner_id == owner_id)

        result = await self.session.execute(query)
        proxies = list(result.scalars().all())

        # Обновляем кэш
        if self._redis and proxies:
            await self._cache_working_ids(proxies)

        return proxies

    async def get_proxy_for_account(
        self, account_id: UUID
    ) -> Optional[Proxy]:
        """Получить прокси, привязанный к аккаунту."""
        result = await self.session.execute(
            select(Proxy)
            .options(selectinload(Proxy.accounts))
            .join(Proxy.accounts)
            .where(Account.id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_stats(self, owner_id: UUID) -> ProxyStats:
        """Получить сводную статистику по прокси."""
        # Общие метрики
        result = await self.session.execute(
            select(
                func.count(Proxy.id).label("total"),
                func.count(Proxy.id).filter(Proxy.is_active.is_(True)).label("active"),
                func.count(Proxy.id).filter(Proxy.is_working.is_(True)).label("working"),
                func.count(Proxy.id).filter(Proxy.is_working.is_(False)).label("failing"),
                func.count(Proxy.id)
                .filter(Proxy.is_working.is_(None))
                .label("unchecked"),
                func.count(Proxy.id)
                .filter(Proxy.scheme == "http")
                .label("http_count"),
                func.count(Proxy.id)
                .filter(Proxy.scheme == "socks5")
                .label("socks5_count"),
                func.count(Proxy.id)
                .filter(Proxy.scheme == "mtproto")
                .label("mtproto_count"),
                func.avg(Proxy.ping_ms)
                .filter(Proxy.is_working.is_(True))
                .label("avg_ping_ms"),
            ).where(Proxy.owner_id == owner_id)
        )
        row = result.one()

        # Аккаунты на прокси
        in_use_result = await self.session.execute(
            select(func.count(Account.id)).where(
                Account.proxy_id.isnot(None),
                Account.owner_id == owner_id,
            )
        )
        in_use_total = in_use_result.scalar_one()

        return ProxyStats(
            total=row.total,
            active=row.active,
            working=row.working,
            failing=row.failing,
            unchecked=row.unchecked,
            http_count=row.http_count,
            socks5_count=row.socks5_count,
            mtproto_count=row.mtproto_count,
            avg_ping_ms=float(row.avg_ping_ms) if row.avg_ping_ms else None,
            in_use_total=in_use_total,
        )

    # ================================================================== #
    #   UPDATE
    # ================================================================== #

    async def update_proxy(
        self, proxy: Proxy, data: ProxyUpdate
    ) -> Proxy:
        """Обновить прокси."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(proxy, field):
                setattr(proxy, field, value)

        await self.session.commit()
        await self.session.refresh(proxy)

        log = _LOGGER.bind(proxy_id=str(proxy.id))
        log.info("Proxy updated", fields=list(update_data.keys()))

        # Если изменились параметры подключения — перетестировать
        if any(f in update_data for f in ("scheme", "host", "port", "username", "password", "secret")):
            proxy.is_working = None
            proxy.ping_ms = None
            proxy.status_message = "Pending re-check after update"
            await self.session.commit()
            asyncio.create_task(self._auto_test_after_create(proxy))

        return proxy

    async def update_status_after_test(
        self,
        proxy_id: UUID,
        is_working: bool,
        ping_ms: Optional[float],
        status_message: Optional[str],
    ) -> None:
        """Обновить статус прокси после проверки."""
        await self.session.execute(
            update(Proxy)
            .where(Proxy.id == proxy_id)
            .values(
                is_working=is_working,
                ping_ms=ping_ms,
                status_message=status_message,
                last_checked_at=datetime.now(timezone.utc),
            )
        )
        await self.session.commit()

        # Инвалидируем кэш
        if self._redis:
            await self._redis.delete(WORKING_PROXIES_CACHE_KEY)

        log = _LOGGER.bind(proxy_id=str(proxy_id))
        log.info("Proxy status updated after test", working=is_working, ping_ms=ping_ms)

    # ================================================================== #
    #   DELETE
    # ================================================================== #

    async def delete_proxy(self, proxy: Proxy) -> bool:
        """Удалить прокси с проверкой на использование аккаунтами.

        Raises:
            ValueError: если прокси используется хотя бы одним активным аккаунтом.
        """
        # Проверяем использование активными аккаунтами
        active_accounts = [a for a in (proxy.accounts or []) if a.is_active]

        if active_accounts:
            account_names = [a.display_name for a in active_accounts]
            raise ValueError(
                f"Cannot delete proxy '{proxy.title}': "
                f"it is used by {len(active_accounts)} active account(s): "
                f"{', '.join(account_names[:5])}"
                + ("..." if len(active_accounts) > 5 else "")
            )

        log = _LOGGER.bind(proxy_id=str(proxy.id), fp=proxy.display_name)
        log.info(
            "Deleting proxy",
            accounts_count=len(proxy.accounts or []),
        )

        await self.session.delete(proxy)
        await self.session.commit()

        # Инвалидируем кэш
        if self._redis:
            await self._redis.delete(WORKING_PROXIES_CACHE_KEY)

        log.info("Proxy deleted")
        return True

    # ================================================================== #
    #   TEST
    # ================================================================== #

    async def test_proxy(
        self, proxy: Optional[Proxy] = None, *, host: Optional[str] = None,
        port: Optional[int] = None, scheme: Optional[str] = None,
        username: Optional[str] = None, password: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> ProxyTestResult:
        """Проверить работоспособность прокси.

        Поддерживает все типы прокси:
        - HTTP / SOCKS5: проверка через httpx + socket
        - MTProto: только проверка доступности хоста/порта (без Telegram DC)
        """
        if proxy:
            host = proxy.host
            port = proxy.port
            scheme = proxy.scheme
            username = proxy.username
            password = proxy.password
            secret = proxy.secret

        # Простая проверка: resolve + TCP connect + тайминг
        result = await self._test_proxy_connection(
            host=host,
            port=port,
            scheme=scheme or "socks5",
            username=username,
            password=password,
            secret=secret,
        )

        # Если прокси существует в БД — обновляем статус
        if proxy:
            await self._update_test_result(proxy, result)

        return result

    async def _test_proxy_connection(
        self,
        host: str,
        port: int,
        scheme: str = "socks5",
        username: Optional[str] = None,
        password: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> ProxyTestResult:
        """Внутренняя проверка подключения к прокси.

        Стратегия:
        1. DNS resolve хоста
        2. TCP connect к порту с замером времени
        3. Для HTTP: проверка ответа через httpx
        4. Для SOCKS5: проверка через socks-библиотеку
        5. Для MTProto: только TCP connect
        """
        start_time = time.monotonic()

        # Шаг 1: DNS resolve
        try:
            resolved = await asyncio.get_event_loop().getaddrinfo(
                host, port, family=socket.AF_INET, type=socket.SOCK_STREAM
            )
            if not resolved:
                return ProxyTestResult(
                    host=host,
                    port=port,
                    scheme=scheme,
                    is_working=False,
                    error_message=f"DNS resolution failed for {host}",
                )
            ip = resolved[0][4][0]
        except (socket.gaierror, OSError) as exc:
            return ProxyTestResult(
                host=host,
                port=port,
                scheme=scheme,
                is_working=False,
                error_message=f"DNS resolution error: {exc}",
            )

        # Шаг 2: TCP connect с таймаутом
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host=ip, port=port),
                timeout=PROXY_TEST_TIMEOUT,
            )
            writer.close()
            await writer.wait_closed()
        except asyncio.TimeoutError:
            return ProxyTestResult(
                host=host,
                port=port,
                scheme=scheme,
                is_working=False,
                error_message=f"Connection timeout after {PROXY_TEST_TIMEOUT}s",
            )
        except (ConnectionRefusedError, OSError) as exc:
            return ProxyTestResult(
                host=host,
                port=port,
                scheme=scheme,
                is_working=False,
                error_message=f"Connection refused: {exc}",
            )
        except Exception as exc:
            return ProxyTestResult(
                host=host,
                port=port,
                scheme=scheme,
                is_working=False,
                error_message=str(exc),
            )

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 1)

        # Шаг 3: Для HTTP — попробуем сделать запрос через httpx
        if scheme == "http":
            http_ok, http_error = await self._test_http_proxy(host, port, username, password)
            if not http_ok:
                return ProxyTestResult(
                    host=host,
                    port=port,
                    scheme=scheme,
                    is_working=False,
                    ping_ms=elapsed_ms,
                    error_message=http_error,
                )

        # Успех
        return ProxyTestResult(
            host=host,
            port=port,
            scheme=scheme,
            is_working=True,
            ping_ms=elapsed_ms,
            error_message=None,
        )

    async def _test_http_proxy(
        self,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """Проверить HTTP-прокси через запрос к тестовому серверу."""
        try:
            import httpx
            proxy_url = f"http://{host}:{port}"
            if username and password:
                proxy_url = f"http://{username}:{password}@{host}:{port}"

            async with httpx.AsyncClient(
                proxies={"http://": proxy_url, "https://": proxy_url},
                timeout=5.0,
            ) as client:
                resp = await client.get("http://httpbin.org/ip", timeout=5.0)
                if resp.status_code == 200:
                    return True, None
                return False, f"HTTP proxy returned {resp.status_code}"
        except ImportError:
            # httpx не установлен — пропускаем HTTP-проверку
            return True, None
        except Exception as exc:
            return False, f"HTTP proxy test failed: {exc}"

    async def test_bulk(
        self, proxy_ids: list[UUID]
    ) -> list[ProxyTestResult]:
        """Массовое тестирование прокси."""
        # Загружаем прокси из БД
        result = await self.session.execute(
            select(Proxy).where(Proxy.id.in_(proxy_ids))
        )
        proxies = list(result.scalars().all())

        # Тестируем параллельно (с ограничением)
        sem = asyncio.Semaphore(10)

        async def test_with_sem(proxy: Proxy) -> ProxyTestResult:
            async with sem:
                return await self.test_proxy(proxy=proxy)

        tasks = [test_with_sem(p) for p in proxies]
        results = await asyncio.gather(*tasks)

        log = _LOGGER.bind(
            tested=len(results),
            working=sum(1 for r in results if r.is_working),
        )
        log.info("Bulk test completed")

        return list(results)

    async def _update_test_result(
        self, proxy: Proxy, result: ProxyTestResult
    ) -> None:
        """Обновить поля прокси по результату теста."""
        proxy.is_working = result.is_working
        proxy.ping_ms = result.ping_ms
        proxy.status_message = result.error_message
        proxy.last_checked_at = datetime.now(timezone.utc)

        await self.session.commit()

        # Инвалидируем кэш
        if self._redis:
            await self._redis.delete(WORKING_PROXIES_CACHE_KEY)

    # ================================================================== #
    #   REDIS CACHE
    # ================================================================== #

    async def _cache_working_ids(self, proxies: list[Proxy]) -> None:
        """Скэшировать ID рабочих прокси в Redis."""
        if not self._redis:
            return
        try:
            ids = [str(p.id) for p in proxies if p.is_working]
            if ids:
                await self._redis.sadd(WORKING_PROXIES_CACHE_KEY, *ids)
                await self._redis.expire(WORKING_PROXIES_CACHE_KEY, WORKING_PROXIES_CACHE_TTL)
        except Exception as exc:
            _LOGGER.warning("Failed to cache working proxies", error=str(exc))

    async def _get_cached_working_ids(
        self, owner_id: Optional[UUID] = None
    ) -> Optional[list[UUID]]:
        """Получить ID рабочих прокси из кэша."""
        if not self._redis:
            return None
        try:
            raw_ids = await self._redis.smembers(WORKING_PROXIES_CACHE_KEY)
            if raw_ids:
                return [UUID(rid) for rid in raw_ids]
            return None
        except Exception:
            return None

    async def invalidate_cache(self) -> None:
        """Инвалидировать кэш рабочих прокси."""
        if self._redis:
            await self._redis.delete(WORKING_PROXIES_CACHE_KEY)
            _LOGGER.debug("Working proxies cache invalidated")

    # ================================================================== #
    #   VALIDATION
    # ================================================================== #

    @staticmethod
    def validate_proxy_string(
        proxy_string: str,
    ) -> tuple[str, str, int, Optional[str], Optional[str]]:
        """Разобрать строку прокси и вернуть (scheme, host, port, username, password).

        Формат: scheme://[user:password@]host:port
        """
        # Убираем пробелы
        proxy_string = proxy_string.strip()

        scheme = "socks5"
        username = None
        password = None
        rest = proxy_string

        # Определяем схему
        scheme_match = re.match(r"^(https?|socks5|mtproto)://(.+)$", proxy_string, re.IGNORECASE)
        if scheme_match:
            scheme = scheme_match.group(1).lower()
            rest = scheme_match.group(2)

        # Определяем credentials и host:port
        auth_match = re.match(r"^(?:([^:@]+)(?::([^@]*))?@)?(.+)$", rest)
        if auth_match:
            username = auth_match.group(1)
            password = auth_match.group(2)
            host_part = auth_match.group(3)
        else:
            host_part = rest

        # Определяем host:port
        host_port_match = re.match(r"^([a-zA-Z0-9.-]+|\[?[a-fA-F0-9:]+\]?):(\d+)$", host_part)
        if not host_port_match:
            raise ValueError(f"Invalid proxy format: {proxy_string}")

        host = host_port_match.group(1)
        port = int(host_port_match.group(2))

        return scheme, host, port, username, password

    # ================================================================== #
    #   UTILITY
    # ================================================================== #

    @staticmethod
    def count_active_accounts_in_proxies(proxies: list[Proxy]) -> int:
        """Подсчитать общее количество активных аккаунтов на списке прокси."""
        total = 0
        for p in proxies:
            total += p.active_accounts_count
        return total