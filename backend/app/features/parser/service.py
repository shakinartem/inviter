"""
Сервис парсинга чатов и пользователей по нише.

ParserService:
- search_chats() — основной метод парсинга (Telegram / TGStat)
- save_parsed_chats() — сохранение с дедупликацией
- get_chats_for_invite() — получение чатов для инвайтинга
- export_chats_to_csv() — экспорт в CSV
- Кэширование в Redis (TTL 1-2 часа)
- Async Semaphore для ограничения параллельных запросов
- Логирование с logger.bind(owner_id=..., query=...)
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel, Chat, User

from app.db.session import AsyncSessionLocal, get_db_session
from app.features.parser.models import ParsedChat, ParsedUser
from app.features.parser.schemas import (
    ParsedChatCreate,
    ParserSearchRequest,
    ParserStats,
)
from app.features.telegram.client_manager import TelegramClientManager


# ==================== Constants ====================

CACHE_TTL_CHATS = 7200  # 2 часа для списков
CACHE_TTL_STATS = 3600  # 1 час для статистики
CACHE_PREFIX = "parser:chats"
CACHE_STATS_PREFIX = "parser:stats"

DEFAULT_SEMAPHORE_LIMIT = 5
"""Максимум параллельных запросов к внешним источникам."""

TGSTAT_BASE_URL = "https://tgstat.ru"
TGSTAT_SEARCH_URL = f"{TGSTAT_BASE_URL}/search"
TGSTAT_TIMEOUT = 30

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


# ==================== Service ====================


class ParserService:
    """Сервис для парсинга Telegram-чатов и пользователей по нише.

    Поддерживает источники:
    - telegram — глобальный поиск Telegram (SearchGlobal / SearchRequest)
    - tgstat — парсинг TGStat (httpx + BeautifulSoup)
    - telemetr — заглушка для будущей реализации
    """

    def __init__(
        self,
        redis: Optional[Redis] = None,
        semaphore_limit: int = DEFAULT_SEMAPHORE_LIMIT,
    ) -> None:
        self._redis = redis
        self._semaphore = asyncio.Semaphore(semaphore_limit)
        self._tg_client_manager = TelegramClientManager()
        self._http_client: Optional[httpx.AsyncClient] = None

        logger.bind(module="parser").info(
            "ParserService initialized",
            redis=redis is not None,
            semaphore_limit=semaphore_limit,
        )

    # ===================================================================== #
    # HTTP client
    # ===================================================================== #
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Ленивое создание HTTP-клиента с ротацией User-Agent."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(TGSTAT_TIMEOUT),
                follow_redirects=True,
                headers={"User-Agent": USER_AGENTS[0]},
            )
        return self._http_client

    async def close(self) -> None:
        """Закрыть HTTP-клиент."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def create_mock_parsed_users(
        self,
        owner_id: UUID,
        db_session: AsyncSession,
        title: str,
        count: int = 10,
        username_prefix: str = "mock_user",
        include_bots: bool = False,
        include_scam: bool = False,
        include_fake: bool = False,
    ) -> ParsedChat:
        chat = ParsedChat(
            owner_id=owner_id,
            chat_id=-(
                abs(hash(f"{owner_id}:{title}:{datetime.now(timezone.utc).timestamp()}"))
                % 10_000_000_000
            ),
            username=username_prefix,
            title=title,
            chat_type="manual",
            participants_count=count,
            active_participants=count,
            source="manual",
            is_public=False,
            is_active=True,
            last_parsed_at=datetime.now(timezone.utc),
            extra_data={"mock": True, "username_prefix": username_prefix},
        )
        db_session.add(chat)
        await db_session.flush()

        for index in range(1, count + 1):
            db_session.add(
                ParsedUser(
                    owner_id=owner_id,
                    chat_id=chat.id,
                    user_id=10_000_000 + index,
                    username=f"{username_prefix}_{index}",
                    first_name=f"Mock {index}",
                    status="member",
                    is_bot=include_bots and index % 10 == 0,
                    is_scam=include_scam and index % 15 == 0,
                    is_fake=include_fake and index % 20 == 0,
                )
            )

        await db_session.commit()
        await db_session.refresh(chat)
        return chat

    # ===================================================================== #
    # Main search method
    # ===================================================================== #
    async def search_chats(
        self,
        request: ParserSearchRequest,
        owner_id: UUID,
        db_session: Optional[AsyncSession] = None,
    ) -> list[ParsedChat]:
        """Основной метод парсинга чатов по нише.

        В зависимости от source выбирает стратегию поиска:
        - telegram → SearchGlobal через Telethon
        - tgstat → парсинг TGStat.com
        - telemetr → заглушка

        Возвращает список сохранённых/обновлённых ParsedChat.
        """
        log = logger.bind(owner_id=str(owner_id), query=request.query, source=request.source)
        log.info("Starting chat search")

        # Проверка кэша
        if self._redis:
            cached = await self._get_cached_chats(request, owner_id)
            if cached is not None:
                log.info("Returning cached results", count=len(cached))
                return cached

        start_time = time.monotonic()

        async with self._semaphore:
            try:
                if request.source == "telegram":
                    chats = await self._search_telegram(request, owner_id, log)
                elif request.source == "tgstat":
                    chats = await self._search_tgstat(request, owner_id, log)
                elif request.source == "telemetr":
                    chats = await self._search_telemetr(request, owner_id, log)
                else:
                    raise ValueError(f"Unsupported source: {request.source}")

            except Exception as exc:
                log.error("Search failed", error=str(exc))
                raise

        # Фильтрация по участникам
        chats = self._filter_by_participants(chats, request)

        # Сохранение
        saved_chats = await self.save_parsed_chats(chats, owner_id, db_session)

        # Кэширование
        if self._redis:
            await self._cache_chats(request, owner_id, saved_chats)

        duration = time.monotonic() - start_time
        log.info(
            "Search completed",
            found=len(chats),
            saved=len(saved_chats),
            duration_seconds=round(duration, 2),
        )

        return saved_chats

    # ===================================================================== #
    # Telegram search (SearchGlobal)
    # ===================================================================== #
    async def _search_telegram(
        self,
        request: ParserSearchRequest,
        owner_id: UUID,
        log: Any,
    ) -> list[ParsedChatCreate]:
        """Поиск чатов через глобальный поиск Telegram (SearchRequest).

        Использует существующий TelegramClient из менеджера.
        """
        log.info("Searching Telegram global")
        chats: list[ParsedChatCreate] = []

        # Получаем первый доступный аккаунт пользователя для поиска
        account = await self._get_account_for_search(owner_id)
        if account is None:
            log.warning("No active account available for Telegram search")
            return chats

        try:
            client: TelegramClient = await self._tg_client_manager.get_client(account)
        except Exception as exc:
            log.error("Failed to get Telegram client", error=str(exc))
            return chats

        try:
            # Используем SearchRequest для глобального поиска
            result = await client(SearchRequest(
                q=request.query,
                limit=min(request.limit, 200),
            ))

            for chat in result.chats:
                if not isinstance(chat, (Channel, Chat)):
                    continue

                if isinstance(chat, User):
                    continue

                if request.chat_type:
                    chat_type = self._resolve_chat_type(chat)
                    if chat_type != request.chat_type:
                        continue

                chat_data = self._parse_telegram_chat(chat, request)
                if chat_data:
                    chats.append(chat_data)

        except FloodWaitError as exc:
            log.warning("FloodWait in Telegram search", seconds=exc.seconds)
            raise
        except Exception as exc:
            log.error("Telegram search error", error=str(exc))
        finally:
            await self._tg_client_manager.release_client(client)

        log.info("Telegram search results", found=len(chats))
        return chats

    def _resolve_chat_type(self, chat: Any) -> str:
        """Определить тип чата из объекта Telethon."""
        if hasattr(chat, "broadcast") and chat.broadcast:
            return "channel"
        if hasattr(chat, "megagroup") and chat.megagroup:
            return "supergroup"
        if isinstance(chat, Chat):
            return "group"
        return "chat"

    def _parse_telegram_chat(
        self,
        chat: Any,
        request: ParserSearchRequest,
    ) -> Optional[ParsedChatCreate]:
        """Преобразовать объект Telethon в ParsedChatCreate."""
        chat_id = getattr(chat, "id", 0)
        if not chat_id:
            return None

        username = getattr(chat, "username", None)
        title = getattr(chat, "title", None)
        if not title:
            title = getattr(chat, "first_name", None) or f"Chat {chat_id}"

        participants = getattr(chat, "participants_count", None)
        if participants is None:
            participants = getattr(chat, "members_count", None)

        chat_type = self._resolve_chat_type(chat)

        return ParsedChatCreate(
            chat_id=(-chat_id if chat_id > 0 else chat_id),
            username=username,
            title=title,
            description=getattr(chat, "about", None),
            access_hash=str(getattr(chat, "access_hash", "")) if getattr(chat, "access_hash", None) else None,
            chat_type=chat_type,
            participants_count=participants,
            is_public=username is not None,
            source="telegram_search",
            niche=request.query,
            language=request.language,
            country=request.country,
        )

    # ===================================================================== #
    # TGStat search
    # ===================================================================== #
    async def _search_tgstat(
        self,
        request: ParserSearchRequest,
        owner_id: UUID,
        log: Any,
    ) -> list[ParsedChatCreate]:
        """Парсинг TGStat.com через HTTP + BeautifulSoup."""
        log.info("Searching TGStat")
        chats: list[ParsedChatCreate] = []

        client = await self._get_http_client()

        try:
            params = {
                "q": request.query,
                "lang": request.language or "all",
                "type": "channels",
            }
            resp = await client.get(TGSTAT_SEARCH_URL, params=params)

            if resp.status_code != 200:
                log.warning("TGStat returned non-200", status=resp.status_code)
                return chats

            soup = BeautifulSoup(resp.text, "html.parser")

            for card in soup.select("div.card, div.channel-item, div.search-item"):
                try:
                    chat_data = self._parse_tgstat_card(card, request)
                    if chat_data:
                        chats.append(chat_data)
                except Exception as parse_err:
                    log.debug("Failed to parse TGStat card", error=str(parse_err))
                    continue

            if request.limit > len(chats):
                next_page = soup.select_one("a[rel='next'], a.next-page")
                if next_page and next_page.get("href"):
                    try:
                        more_chats = await self._parse_tgstat_page(
                            str(next_page["href"]),
                            request,
                            log,
                        )
                        chats.extend(more_chats)
                    except Exception as exc:
                        log.debug("Failed to parse TGStat next page", error=str(exc))

        except httpx.TimeoutException:
            log.warning("TGStat request timed out")
        except httpx.HTTPStatusError as exc:
            log.warning("TGStat HTTP error", status=exc.response.status_code)
        except Exception as exc:
            log.error("TGStat search error", error=str(exc))

        log.info("TGStat search results", found=len(chats))
        return chats

    def _parse_tgstat_card(
        self,
        card: Any,
        request: ParserSearchRequest,
    ) -> Optional[ParsedChatCreate]:
        """Парсинг одной карточки чата с TGStat."""
        title_el = card.select_one("a.channel-title, h5 a, .title a")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        href = title_el.get("href", "")
        username = None
        chat_id = 0
        if "/" in href:
            username = href.rsplit("/", 1)[-1].lstrip("@")
            chat_id = abs(hash(f"tgstat_{username}")) % (10**10) * -1

        desc_el = card.select_one("p.description, .description, .channel-description")
        description = desc_el.get_text(strip=True) if desc_el else None

        members_el = card.select_one(
            ".subscribers, .members, .channel-members, "
            ".stat-item span, .count"
        )
        participants = None
        if members_el:
            participants = self._parse_count(members_el.get_text(strip=True))

        cat_el = card.select_one(".category, .channel-category, a.tag")
        category = cat_el.get_text(strip=True) if cat_el else None

        lang_el = card.select_one(".language, .channel-lang")
        language = lang_el.get_text(strip=True)[:10] if lang_el else request.language

        return ParsedChatCreate(
            chat_id=chat_id,
            username=username,
            title=title,
            description=description,
            participants_count=participants,
            category=category,
            niche=request.query,
            source="tgstat",
            language=language or request.language,
            country=request.country,
            is_public=True,
        )

    async def _parse_tgstat_page(
        self,
        path: str,
        request: ParserSearchRequest,
        log: Any,
    ) -> list[ParsedChatCreate]:
        """Парсинг дополнительной страницы TGStat (пагинация)."""
        url = f"{TGSTAT_BASE_URL}{path}" if path.startswith("/") else path
        client = await self._get_http_client()
        resp = await client.get(url)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        chats = []
        for card in soup.select("div.card, div.channel-item, div.search-item"):
            try:
                chat_data = self._parse_tgstat_card(card, request)
                if chat_data:
                    chats.append(chat_data)
            except Exception:
                continue
        return chats

    # ===================================================================== #
    # Telemetr search (stub)
    # ===================================================================== #
    async def _search_telemetr(
        self,
        request: ParserSearchRequest,
        owner_id: UUID,
        log: Any,
    ) -> list[ParsedChatCreate]:
        """Заглушка для Telemetr."""
        log.warning("Telemetr search is not yet implemented")
        return []

    # ===================================================================== #
    # Filter helpers
    # ===================================================================== #
    def _filter_by_participants(
        self,
        chats: list[ParsedChatCreate],
        request: ParserSearchRequest,
    ) -> list[ParsedChatCreate]:
        """Отфильтровать чаты по количеству участников."""
        if request.min_participants <= 0 and request.max_participants <= 0:
            return chats

        filtered = []
        for chat in chats:
            count = chat.participants_count or 0
            if count < request.min_participants:
                continue
            if request.max_participants > 0 and count > request.max_participants:
                continue
            filtered.append(chat)
        return filtered

    def _parse_count(self, text: str) -> Optional[int]:
        """Распарсить количество из строки вида '12 345', '1.2K', '1M'."""
        text = text.strip().lower().replace(" ", "").replace(",", ".")
        if not text:
            return None

        multipliers = {"k": 1000, "m": 1000000, "b": 1000000000}
        multiplier = 1
        for suffix, mult in multipliers.items():
            if text.endswith(suffix):
                multiplier = mult
                text = text[:-1]
                break

        try:
            val = float(text) * multiplier
            return int(val)
        except (ValueError, TypeError):
            digits = re.sub(r"[^\d]", "", text)
            return int(digits) if digits else None

    # ===================================================================== #
    # Save parsed chats (deduplication)
    # ===================================================================== #
    async def save_parsed_chats(
        self,
        chats: list[ParsedChatCreate],
        owner_id: UUID,
        db_session: Optional[AsyncSession] = None,
    ) -> list[ParsedChat]:
        """Сохранить спарсенные чаты в БД с дедупликацией.

        Если чат с таким chat_id уже существует — обновляет поля.
        Если нет — создаёт новый.
        """
        if not chats:
            return []

        log = logger.bind(owner_id=str(owner_id))
        close_session = False

        if db_session is None:
            db_session = AsyncSessionLocal()
            close_session = True

        try:
            saved = []
            now = datetime.now(timezone.utc)

            for chat_data in chats:
                existing = await self._find_chat_by_telegram_id(
                    db_session, chat_data.chat_id, owner_id
                )

                if existing:
                    updated = await self._update_existing_chat(
                        db_session, existing, chat_data, now, log
                    )
                    saved.append(updated)
                else:
                    new_chat = await self._create_new_chat(
                        db_session, chat_data, owner_id, now, log
                    )
                    saved.append(new_chat)

            await db_session.commit()
            log.info("Saved parsed chats", total=len(saved))

        except Exception as exc:
            await db_session.rollback()
            log.error("Failed to save parsed chats", error=str(exc))
            raise
        finally:
            if close_session:
                await db_session.close()

        return saved

    async def _find_chat_by_telegram_id(
        self,
        db_session: AsyncSession,
        chat_id: int,
        owner_id: UUID,
    ) -> Optional[ParsedChat]:
        """Найти чат по telegram_id и владельцу."""
        stmt = select(ParsedChat).where(
            ParsedChat.chat_id == chat_id,
            ParsedChat.owner_id == owner_id,
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def _update_existing_chat(
        self,
        db_session: AsyncSession,
        existing: ParsedChat,
        chat_data: ParsedChatCreate,
        now: datetime,
        log: Any,
    ) -> ParsedChat:
        """Обновить поля существующего чата."""
        update_fields = {
            "title": chat_data.title,
            "username": chat_data.username,
            "description": chat_data.description,
            "chat_type": chat_data.chat_type,
            "participants_count": chat_data.participants_count,
            "active_participants": chat_data.active_participants,
            "category": chat_data.category,
            "niche": chat_data.niche,
            "tags": chat_data.tags,
            "language": chat_data.language,
            "country": chat_data.country,
            "is_public": chat_data.is_public,
            "is_active": chat_data.is_active,
            "is_restricted": chat_data.is_restricted,
            "avg_posts_per_day": chat_data.avg_posts_per_day,
            "avg_reach_per_post": chat_data.avg_reach_per_post,
            "engagement_rate": chat_data.engagement_rate,
            "extra_data": chat_data.extra_data,
        }

        changed = False
        for field, value in update_fields.items():
            if value is not None:
                setattr(existing, field, value)
                changed = True

        if chat_data.access_hash and not existing.access_hash:
            existing.access_hash = chat_data.access_hash
            changed = True

        existing.last_parsed_at = now
        existing.parse_count = (existing.parse_count or 0) + 1

        if changed:
            log.debug("Updated chat", chat_id=existing.chat_id, title=existing.title)

        return existing

    async def _create_new_chat(
        self,
        db_session: AsyncSession,
        chat_data: ParsedChatCreate,
        owner_id: UUID,
        now: datetime,
        log: Any,
    ) -> ParsedChat:
        """Создать новый ParsedChat из данных."""
        new_chat = ParsedChat(
            owner_id=owner_id,
            chat_id=chat_data.chat_id,
            username=chat_data.username,
            title=chat_data.title,
            description=chat_data.description,
            access_hash=chat_data.access_hash,
            chat_type=chat_data.chat_type,
            participants_count=chat_data.participants_count,
            active_participants=chat_data.active_participants,
            category=chat_data.category,
            niche=chat_data.niche,
            tags=chat_data.tags,
            language=chat_data.language,
            country=chat_data.country,
            is_public=chat_data.is_public or False,
            is_active=chat_data.is_active,
            is_restricted=chat_data.is_restricted,
            source=chat_data.source,
            last_parsed_at=now,
            parse_count=1,
            avg_posts_per_day=chat_data.avg_posts_per_day,
            avg_reach_per_post=chat_data.avg_reach_per_post,
            engagement_rate=chat_data.engagement_rate,
            extra_data=chat_data.extra_data,
        )
        db_session.add(new_chat)
        log.debug("Created new chat", chat_id=new_chat.chat_id, title=new_chat.title)
        return new_chat

    # ===================================================================== #
    # Get chats for invite
    # ===================================================================== #
    async def get_chats_for_invite(
        self,
        niche: str,
        limit: int = 50,
        owner_id: Optional[UUID] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> list[ParsedChat]:
        """Получить чаты для инвайтинга по нише.

        Возвращает активные, публичные чаты с фильтром по нише/category.
        """
        log = logger.bind(niche=niche, limit=limit)
        close_session = False

        if db_session is None:
            db_session = AsyncSessionLocal()
            close_session = True

        try:
            stmt = (
                select(ParsedChat)
                .where(
                    ParsedChat.is_active == True,
                    or_(
                        ParsedChat.niche.ilike(f"%{niche}%"),
                        ParsedChat.category.ilike(f"%{niche}%"),
                    ),
                )
                .order_by(ParsedChat.participants_count.desc().nullslast())
                .limit(limit)
            )

            if owner_id:
                stmt = stmt.where(ParsedChat.owner_id == owner_id)

            result = await db_session.execute(stmt)
            chats = list(result.scalars().all())
            log.info("Got chats for invite", count=len(chats))
            return chats

        finally:
            if close_session:
                await db_session.close()

    # ===================================================================== #
    # Export to CSV
    # ===================================================================== #
    async def export_chats_to_csv(
        self,
        owner_id: UUID,
        filters: Optional[dict[str, Any]] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> str:
        """Экспортировать спарсенные чаты в CSV строку."""
        close_session = False
        if db_session is None:
            db_session = AsyncSessionLocal()
            close_session = True

        try:
            stmt = select(ParsedChat).where(ParsedChat.owner_id == owner_id)

            if filters:
                if filters.get("category"):
                    stmt = stmt.where(ParsedChat.category == filters["category"])
                if filters.get("niche"):
                    stmt = stmt.where(ParsedChat.niche == filters["niche"])
                if filters.get("source"):
                    stmt = stmt.where(ParsedChat.source == filters["source"])
                if filters.get("language"):
                    stmt = stmt.where(ParsedChat.language == filters["language"])
                if filters.get("is_active") is not None:
                    stmt = stmt.where(ParsedChat.is_active == filters["is_active"])

            stmt = stmt.order_by(ParsedChat.participants_count.desc().nullslast())
            result = await db_session.execute(stmt)
            chats = list(result.scalars().all())

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "chat_id", "username", "title", "description",
                "chat_type", "participants_count", "active_participants",
                "category", "niche", "language", "country",
                "is_public", "is_active", "source", "last_parsed_at",
            ])

            for chat in chats:
                writer.writerow([
                    chat.chat_id,
                    chat.username or "",
                    chat.title or "",
                    (chat.description or "")[:500],
                    chat.chat_type or "",
                    chat.participants_count or 0,
                    chat.active_participants or 0,
                    chat.category or "",
                    chat.niche or "",
                    chat.language or "",
                    chat.country or "",
                    chat.is_public,
                    chat.is_active,
                    chat.source,
                    chat.last_parsed_at.isoformat() if chat.last_parsed_at else "",
                ])

            csv_content = output.getvalue()
            log.info("Exported chats to CSV", count=len(chats))
            return csv_content

        finally:
            if close_session:
                await db_session.close()

    # ===================================================================== #
    # Stats
    # ===================================================================== #
    async def get_stats(
        self,
        owner_id: UUID,
        db_session: Optional[AsyncSession] = None,
    ) -> ParserStats:
        """Получить сводную статистику по спарсенным чатам."""
        if self._redis:
            cached = await self._redis.get(f"{CACHE_STATS_PREFIX}:{owner_id}")
            if cached:
                return ParserStats.model_validate_json(cached)

        close_session = False
        if db_session is None:
            db_session = AsyncSessionLocal()
            close_session = True

        try:
            total = await self._count_chats(db_session, owner_id)
            active = await self._count_chats(db_session, owner_id, is_active=True)
            by_source = await self._group_count(db_session, ParsedChat.source, owner_id)
            by_category = await self._group_count(db_session, ParsedChat.category, owner_id)
            by_language = await self._group_count(db_session, ParsedChat.language, owner_id)
            total_users = await self._count_users(db_session, owner_id)
            avg_participants = await self._avg_participants(db_session, owner_id)
            total_parses = await self._sum_parses(db_session, owner_id)

            stats = ParserStats(
                total_chats=total,
                active_chats=active,
                total_users=total_users,
                by_source=dict(by_source),
                by_category=dict(by_category),
                by_language=dict(by_language),
                total_parses=total_parses,
                avg_participants=avg_participants,
            )

            if self._redis:
                await self._redis.setex(
                    f"{CACHE_STATS_PREFIX}:{owner_id}",
                    CACHE_TTL_STATS,
                    stats.model_dump_json(),
                )

            return stats

        finally:
            if close_session:
                await db_session.close()

    async def _count_chats(
        self,
        db_session: AsyncSession,
        owner_id: UUID,
        is_active: Optional[bool] = None,
    ) -> int:
        stmt = select(func.count(ParsedChat.id)).where(ParsedChat.owner_id == owner_id)
        if is_active is not None:
            stmt = stmt.where(ParsedChat.is_active == is_active)
        result = await db_session.execute(stmt)
        return result.scalar() or 0

    async def _group_count(
        self,
        db_session: AsyncSession,
        column: Any,
        owner_id: UUID,
    ) -> list[tuple[str, int]]:
        stmt = (
            select(column, func.count(ParsedChat.id))
            .where(ParsedChat.owner_id == owner_id, column.isnot(None))
            .group_by(column)
            .order_by(func.count(ParsedChat.id).desc())
        )
        result = await db_session.execute(stmt)
        return list(result.all())

    async def _count_users(
        self,
        db_session: AsyncSession,
        owner_id: UUID,
    ) -> int:
        stmt = select(func.count(ParsedUser.id)).where(ParsedUser.owner_id == owner_id)
        result = await db_session.execute(stmt)
        return result.scalar() or 0

    async def _avg_participants(
        self,
        db_session: AsyncSession,
        owner_id: UUID,
    ) -> Optional[float]:
        stmt = select(func.avg(ParsedChat.participants_count)).where(
            ParsedChat.owner_id == owner_id,
            ParsedChat.participants_count.isnot(None),
        )
        result = await db_session.execute(stmt)
        val = result.scalar()
        return round(float(val), 2) if val else None

    async def _sum_parses(
        self,
        db_session: AsyncSession,
        owner_id: UUID,
    ) -> int:
        stmt = select(func.sum(ParsedChat.parse_count)).where(ParsedChat.owner_id == owner_id)
        result = await db_session.execute(stmt)
        return result.scalar() or 0

    # ===================================================================== #
    # Delete
    # ===================================================================== #
    async def delete_chat(
        self,
        chat_id: UUID,
        owner_id: UUID,
        db_session: Optional[AsyncSession] = None,
    ) -> bool:
        """Удалить спарсенный чат по ID."""
        close_session = False
        if db_session is None:
            db_session = AsyncSessionLocal()
            close_session = True

        try:
            stmt = select(ParsedChat).where(
                ParsedChat.id == chat_id,
                ParsedChat.owner_id == owner_id,
            )
            result = await db_session.execute(stmt)
            chat = result.scalar_one_or_none()
            if not chat:
                return False

            await db_session.delete(chat)
            await db_session.commit()

            if self._redis:
                await self._redis.delete(f"{CACHE_PREFIX}:{owner_id}")

            logger.info("Deleted parsed chat", chat_id=str(chat_id))
            return True

        except Exception as exc:
            await db_session.rollback()
            logger.error("Failed to delete chat", error=str(exc))
            raise
        finally:
            if close_session:
                await db_session.close()

    async def bulk_delete_chats(
        self,
        chat_ids: list[UUID],
        owner_id: UUID,
        db_session: Optional[AsyncSession] = None,
    ) -> int:
        """Массовое удаление спарсенных чатов."""
        close_session = False
        if db_session is None:
            db_session = AsyncSessionLocal()
            close_session = True

        try:
            stmt = sa_delete(ParsedChat).where(
                ParsedChat.id.in_(chat_ids),
                ParsedChat.owner_id == owner_id,
            )
            result = await db_session.execute(stmt)
            await db_session.commit()

            deleted = result.rowcount

            if self._redis:
                await self._redis.delete(f"{CACHE_PREFIX}:{owner_id}")

            logger.info("Bulk deleted chats", count=deleted)
            return deleted

        except Exception as exc:
            await db_session.rollback()
            logger.error("Failed to bulk delete chats", error=str(exc))
            raise
        finally:
            if close_session:
                await db_session.close()

    # ===================================================================== #
    # Caching
    # ===================================================================== #
    async def _get_cached_chats(
        self,
        request: ParserSearchRequest,
        owner_id: UUID,
    ) -> Optional[list[ParsedChat]]:
        """Получить закэшированные результаты поиска."""
        if not self._redis:
            return None

        cache_key = self._make_cache_key(request, owner_id)
        cached = await self._redis.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                return data
            except (json.JSONDecodeError, TypeError):
                pass
        return None

    async def _cache_chats(
        self,
        request: ParserSearchRequest,
        owner_id: UUID,
        chats: list[ParsedChat],
    ) -> None:
        """Закэшировать результаты поиска."""
        if not self._redis or not chats:
            return

        cache_key = self._make_cache_key(request, owner_id)
        chat_ids = [str(c.id) for c in chats]
        await self._redis.setex(cache_key, CACHE_TTL_CHATS, json.dumps(chat_ids))

    def _make_cache_key(
        self,
        request: ParserSearchRequest,
        owner_id: UUID,
    ) -> str:
        """Сформировать ключ кэша для запроса."""
        parts = [
            CACHE_PREFIX,
            str(owner_id),
            request.source,
            request.query.lower().replace(" ", "_")[:50],
            str(request.min_participants),
            str(request.max_participants),
            request.language or "any",
            request.country or "any",
            str(request.limit),
        ]
        return ":".join(parts)

    # ===================================================================== #
    # Account helper
    # ===================================================================== #
    async def _get_account_for_search(self, owner_id: UUID) -> Optional[Any]:
        """Получить первый активный аккаунт пользователя для поиска."""
        from app.features.accounts.models import Account

        async with AsyncSessionLocal() as db_session:
            stmt = (
                select(Account)
                .where(
                    Account.owner_id == owner_id,
                    Account.is_active == True,
                    Account.status == "active",
                )
                .limit(1)
            )
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()

    # ===================================================================== #
    # Get / List chats
    # ===================================================================== #
    async def get_chat_by_id(
        self,
        chat_id: UUID,
        owner_id: UUID,
        db_session: Optional[AsyncSession] = None,
    ) -> Optional[ParsedChat]:
        """Получить чат по UUID."""
        close_session = False
        if db_session is None:
            db_session = AsyncSessionLocal()
            close_session = True

        try:
            stmt = select(ParsedChat).where(
                ParsedChat.id == chat_id,
                ParsedChat.owner_id == owner_id,
            )
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()
        finally:
            if close_session:
                await db_session.close()

    async def list_chats(
        self,
        owner_id: UUID,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[dict[str, Any]] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> tuple[list[ParsedChat], int]:
        """Получить список спарсенных чатов с фильтрацией.

        Returns:
            tuple[list[ParsedChat], total_count]
        """
        close_session = False
        if db_session is None:
            db_session = AsyncSessionLocal()
            close_session = True

        try:
            stmt = select(ParsedChat).where(ParsedChat.owner_id == owner_id)
            count_stmt = select(func.count(ParsedChat.id)).where(
                ParsedChat.owner_id == owner_id
            )

            if filters:
                if filters.get("source"):
                    stmt = stmt.where(ParsedChat.source == filters["source"])
                    count_stmt = count_stmt.where(ParsedChat.source == filters["source"])
                if filters.get("category"):
                    stmt = stmt.where(ParsedChat.category == filters["category"])
                    count_stmt = count_stmt.where(
                        ParsedChat.category == filters["category"]
                    )
                if filters.get("niche"):
                    stmt = stmt.where(ParsedChat.niche.ilike(f"%{filters['niche']}%"))
                    count_stmt = count_stmt.where(
                        ParsedChat.niche.ilike(f"%{filters['niche']}%")
                    )
                if filters.get("language"):
                    stmt = stmt.where(ParsedChat.language == filters["language"])
                    count_stmt = count_stmt.where(
                        ParsedChat.language == filters["language"]
                    )
                if filters.get("is_active") is not None:
                    stmt = stmt.where(ParsedChat.is_active == filters["is_active"])
                    count_stmt = count_stmt.where(
                        ParsedChat.is_active == filters["is_active"]
                    )
                if filters.get("search"):
                    search = f"%{filters['search']}%"
                    stmt = stmt.where(
                        or_(
                            ParsedChat.title.ilike(search),
                            ParsedChat.username.ilike(search),
                            ParsedChat.description.ilike(search),
                        )
                    )
                    count_stmt = count_stmt.where(
                        or_(
                            ParsedChat.title.ilike(search),
                            ParsedChat.username.ilike(search),
                            ParsedChat.description.ilike(search),
                        )
                    )
                if filters.get("chat_type"):
                    stmt = stmt.where(ParsedChat.chat_type == filters["chat_type"])
                    count_stmt = count_stmt.where(
                        ParsedChat.chat_type == filters["chat_type"]
                    )

            total_result = await db_session.execute(count_stmt)
            total = total_result.scalar() or 0

            stmt = stmt.offset(skip).limit(limit).order_by(
                ParsedChat.participants_count.desc().nullslast(),
                ParsedChat.created_at.desc(),
            )

            result = await db_session.execute(stmt)
            chats = list(result.scalars().all())

            return chats, total

        finally:
            if close_session:
                await db_session.close()
