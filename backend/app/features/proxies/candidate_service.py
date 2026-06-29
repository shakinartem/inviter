"""
Сервис для управления ProxyCandidate.

Предоставляет:
- Импорт MTProto-прокси из текста (parse + create candidates)
- Импорт обычных прокси из текста (socks5, http)
- Проверка кандидата (TCP connect) для всех типов
- Одобрение кандидата (создание рабочего Proxy) для всех типов
- Отклонение / удаление кандидатов
- Bulk check с scoring
- CRUD для кандидатов
"""

from __future__ import annotations

import asyncio
import re
import socket
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.proxies.candidate_models import ProxyCandidate
from app.features.proxies.candidate_schemas import (
    CandidateListItem,
    CandidateListResponse,
    CandidateResponse,
    MtprotoImportRequest,
    MtprotoImportResult,
    TextImportResult,
)
from app.features.proxies.models import Proxy
from app.features.proxies.mtproto_parser import (
    ParsedMtprotoItem,
    find_mtproto_urls,
    normalize_mtproto_item,
    parse_mtproto_url,
)
from app.features.proxies.schemas import ProxyTestResult
from app.core.config import settings

CANDIDATE_TEST_TIMEOUT = settings.proxy_check_timeout_seconds
BULK_CHECK_MAX = 50

_LOGGER = logger.bind(module="CandidateService")


class CandidateService:
    """Сервис для управления кандидатами прокси."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ================================================================== #
    #   PARSE + IMPORT
    # ================================================================== #

    def parse_mtproto_links(self, text: str) -> list[ParsedMtprotoItem]:
        """Распарсить текст и вернуть список нормализованных MTProto-item'ов.

        Args:
            text: Текст для парсинга.

        Returns:
            Список ParsedMtprotoItem только с валидными записями.
        """
        from app.features.proxies.mtproto_parser import parse_mtproto_text

        result = parse_mtproto_text(text)
        return result.items

    async def import_mtproto_from_text(
        self,
        text: str,
        owner_id: UUID,
        source_name: str | None = None,
        source_type: str = "manual_text",
    ) -> MtprotoImportResult:
        """Импортировать MTProto-прокси из текста.

        Парсит ссылки, создаёт кандидатов, пропускает дубликаты.

        Args:
            text: Текст с MTProto-ссылками.
            owner_id: ID владельца.
            source_name: Опциональное название источника.
            source_type: Тип источника (manual_text, mtproto_text, telegram_channel).

        Returns:
            MtprotoImportResult со статистикой импорта.
        """
        from app.features.proxies.mtproto_parser import parse_mtproto_text

        parse_result = parse_mtproto_text(text)
        valid_items = parse_result.items
        invalid_count = len(parse_result.errors)

        imported_count = 0
        skipped_duplicates = 0
        created_candidates: list[ProxyCandidate] = []

        for item in valid_items:
            # Проверка на дубликат (существующий candidate с тем же host+port+secret)
            exists = await self._find_duplicate_candidate(
                host=item.host,
                port=item.port,
                secret=item.secret,
                owner_id=owner_id,
                proxy_type="mtproto",
            )
            if exists:
                skipped_duplicates += 1
                continue

            # Создаём кандидата
            candidate = ProxyCandidate(
                owner_id=owner_id,
                proxy_type="mtproto",
                host=item.host,
                port=item.port,
                secret=item.secret,
                raw_value=item.raw_url,
                source_type=source_type,
                source_name=source_name,
                status="new",
                score=0,
            )
            self.session.add(candidate)
            created_candidates.append(candidate)
            imported_count += 1

        await self.session.commit()

        _LOGGER.info(
            "MTProto import completed",
            imported=imported_count,
            skipped=skipped_duplicates,
            invalid=invalid_count,
        )

        # Обновляем кандидатов из БД (чтобы получить id, timestamps)
        for c in created_candidates:
            await self.session.refresh(c)

        return MtprotoImportResult(
            found_count=len(valid_items) + invalid_count,
            imported_count=imported_count,
            skipped_duplicates=skipped_duplicates,
            invalid_count=invalid_count,
            candidates=[
                CandidateListItem.from_orm_with_masked_secrets(c)
                for c in created_candidates
            ],
        )

    def _parse_proxy_line(
        self, line: str
    ) -> tuple[str, str, int, Optional[str], Optional[str], Optional[str]]:
        """Распарсить одну строку с прокси.

        Возвращает (proxy_type, host, port, username, password, raw_value).

        Поддерживаемые форматы:
        - socks5://user:pass@host:port
        - socks5://host:port
        - http://user:pass@host:port
        - http://host:port
        - host:port (по умолчанию socks5)
        """
        line = line.strip()
        if not line:
            raise ValueError("Empty line")

        proxy_type = "socks5"
        username = None
        password = None
        host = None
        port = 0

        # Формат: scheme://user:pass@host:port
        url_pattern = re.compile(
            r"^(?:(socks5|http|https)://)?"
            r"(?:([^:@]+)(?::([^@]*))?@)?"
            r"([a-zA-Z0-9.-]+|\[?[a-fA-F0-9:]+\]?)"
            r":(\d{1,5})$"
        )
        match = url_pattern.match(line)
        if match:
            scheme = match.group(1)
            if scheme:
                proxy_type = "http" if scheme == "https" else scheme
            username = match.group(2)
            password = match.group(3)
            host = match.group(4)
            port = int(match.group(5))
        else:
            # Формат: host:port
            simple_match = re.match(r"^([a-zA-Z0-9.-]+):(\d{1,5})$", line)
            if simple_match:
                host = simple_match.group(1)
                port = int(simple_match.group(2))
            else:
                raise ValueError(f"Cannot parse proxy line: {line}")

        if not (1 <= port <= 65535):
            raise ValueError(f"Invalid port: {port}")

        return proxy_type, host, port, username, password, line

    async def import_text(
        self,
        text: str,
        owner_id: UUID,
        source_name: str | None = None,
        source_type: str = "manual_text",
    ) -> TextImportResult:
        """Импортировать обычные прокси (socks5, http) из текста.

        Парсит строки, создаёт кандидатов, пропускает дубликаты.

        Args:
            text: Текст с прокси (построчно).
            owner_id: ID владельца.
            source_name: Опциональное название источника.
            source_type: Тип источника.

        Returns:
            TextImportResult со статистикой импорта.
        """
        lines = text.strip().split("\n")
        imported_count = 0
        skipped_duplicates = 0
        invalid_count = 0
        created_candidates: list[ProxyCandidate] = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                proxy_type, host, port, username, password, raw = self._parse_proxy_line(line)
            except ValueError:
                invalid_count += 1
                continue

            # Проверка на дубликат
            duplicate_key = f"{host}:{port}:{username or ''}"
            exists = await self._find_duplicate_proxy_line(
                host=host,
                port=port,
                username=username,
                owner_id=owner_id,
                proxy_type=proxy_type,
            )
            if exists:
                skipped_duplicates += 1
                continue

            candidate = ProxyCandidate(
                owner_id=owner_id,
                proxy_type=proxy_type,
                host=host,
                port=port,
                username=username,
                password=password,
                raw_value=raw,
                source_type=source_type,
                source_name=source_name,
                status="new",
                score=0,
            )
            self.session.add(candidate)
            created_candidates.append(candidate)
            imported_count += 1

        await self.session.commit()

        _LOGGER.info(
            "Text proxy import completed",
            imported=imported_count,
            skipped=skipped_duplicates,
            invalid=invalid_count,
        )

        for c in created_candidates:
            await self.session.refresh(c)

        return TextImportResult(
            found_count=imported_count + skipped_duplicates + invalid_count,
            imported_count=imported_count,
            skipped_duplicates=skipped_duplicates,
            invalid_count=invalid_count,
            candidates=[
                CandidateListItem.from_orm_with_masked_secrets(c)
                for c in created_candidates
            ],
        )

    async def _find_duplicate_candidate(
        self,
        host: str,
        port: int,
        secret: str | None,
        owner_id: UUID,
        proxy_type: str = "mtproto",
    ) -> bool:
        """Проверить, существует ли уже кандидат с такими host+port+secret."""
        query = select(ProxyCandidate).where(
            ProxyCandidate.host == host,
            ProxyCandidate.port == port,
            ProxyCandidate.owner_id == owner_id,
        )
        # Для MTProto проверяем secret
        if proxy_type == "mtproto":
            query = query.where(ProxyCandidate.secret == secret)
        else:
            query = query.where(ProxyCandidate.proxy_type == proxy_type)

        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def _find_duplicate_proxy_line(
        self,
        host: str,
        port: int,
        username: str | None,
        owner_id: UUID,
        proxy_type: str,
    ) -> bool:
        """Проверить дубликат для обычных прокси."""
        query = select(ProxyCandidate).where(
            ProxyCandidate.host == host,
            ProxyCandidate.port == port,
            ProxyCandidate.proxy_type == proxy_type,
            ProxyCandidate.owner_id == owner_id,
        )
        if username:
            query = query.where(ProxyCandidate.username == username)
        else:
            query = query.where(ProxyCandidate.username.is_(None))

        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    # ================================================================== #
    #   READ
    # ================================================================== #

    async def list_candidates(
        self,
        owner_id: UUID,
        proxy_type: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ProxyCandidate], int]:
        """Получить список кандидатов с фильтрацией и пагинацией."""
        query = (
            select(ProxyCandidate)
            .where(ProxyCandidate.owner_id == owner_id)
        )

        if proxy_type:
            query = query.where(ProxyCandidate.proxy_type == proxy_type)
        if status:
            query = query.where(ProxyCandidate.status == status)

        query = query.order_by(ProxyCandidate.created_at.desc())

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Pagination
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        candidates = list(result.scalars().all())

        return candidates, total

    async def get_candidate(
        self, candidate_id: UUID, owner_id: UUID
    ) -> Optional[ProxyCandidate]:
        """Получить кандидата по ID (с проверкой владельца)."""
        result = await self.session.execute(
            select(ProxyCandidate).where(
                ProxyCandidate.id == candidate_id,
                ProxyCandidate.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_candidate_by_id(self, candidate_id: UUID) -> Optional[ProxyCandidate]:
        """Получить кандидата по ID без проверки владельца."""
        result = await self.session.execute(
            select(ProxyCandidate).where(ProxyCandidate.id == candidate_id)
        )
        return result.scalar_one_or_none()

    # ================================================================== #
    #   CHECK
    # ================================================================== #

    def _calculate_score(
        self,
        is_alive: bool,
        latency_ms: Optional[float],
        proxy_type: str,
        source_type: str,
        repeated_failures: bool = False,
    ) -> int:
        """Рассчитать оценку качества прокси."""
        score = 0
        if is_alive:
            score += 50
        if latency_ms is not None:
            if latency_ms < 1000:
                score += 20
            elif latency_ms < 3000:
                score += 10
        # Тип прокси
        if proxy_type in ("mtproto", "socks5"):
            score += 10
        if proxy_type == "local_adapter":
            score += 15
        # Штраф за публичные/импортированные
        if source_type in ("manual_text", "telegram_channel", "url_list", "mtproto_text"):
            score -= 10
        # Штраф за повторные ошибки
        if repeated_failures:
            score -= 30
        return max(0, score)

    async def check_candidate(
        self, candidate: ProxyCandidate
    ) -> ProxyTestResult:
        """Проверить кандидата любого типа (TCP connect).

        Для всех типов делает TCP connect host:port с таймаутом.
        """
        start_time = time.monotonic()

        # Пытаемся обновить статус на "checking"
        candidate.status = "checking"
        await self.session.commit()

        repeated_failures = candidate.last_error is not None

        # TCP connect
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    host=candidate.host,
                    port=candidate.port,
                ),
                timeout=CANDIDATE_TEST_TIMEOUT,
            )
            writer.close()
            await writer.wait_closed()
        except asyncio.TimeoutError:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 1)
            return self._update_candidate_after_check(
                candidate, False, elapsed_ms,
                f"Connection timeout after {CANDIDATE_TEST_TIMEOUT}s",
            )
        except (ConnectionRefusedError, ConnectionResetError, OSError) as exc:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 1)
            return self._update_candidate_after_check(
                candidate, False, elapsed_ms,
                f"Connection refused: {exc}",
            )
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 1)
            return self._update_candidate_after_check(
                candidate, False, elapsed_ms,
                str(exc),
            )

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 1)
        return self._update_candidate_after_check(
            candidate, True, elapsed_ms, None,
        )

    async def _update_candidate_after_check(
        self,
        candidate: ProxyCandidate,
        is_alive: bool,
        latency_ms: float,
        error_message: str | None,
    ) -> ProxyTestResult:
        """Обновить кандидата после проверки."""
        candidate.status = "alive" if is_alive else "dead"
        candidate.latency_ms = latency_ms
        candidate.last_checked_at = datetime.now(timezone.utc)
        candidate.last_error = error_message
        candidate.score = self._calculate_score(
            is_alive=is_alive,
            latency_ms=latency_ms,
            proxy_type=candidate.proxy_type,
            source_type=candidate.source_type,
            repeated_failures=candidate.last_error is not None and not is_alive,
        )

        return ProxyTestResult(
            proxy_id=candidate.id,
            host=candidate.host,
            port=candidate.port,
            scheme=candidate.proxy_type,
            is_working=is_alive,
            ping_ms=latency_ms,
            error_message=error_message,
        )

    async def check_mtproto_candidate(
        self, candidate: ProxyCandidate
    ) -> ProxyTestResult:
        """Проверить MTProto-кандидата (полная совместимость с существующим кодом).

        Делает TCP connect к host:port с таймаутом.
        """
        return await self.check_candidate(candidate)

    async def check_candidate_by_id(self, candidate_id: UUID, owner_id: UUID) -> ProxyTestResult:
        """Проверить кандидата по ID."""
        candidate = await self.get_candidate(candidate_id, owner_id)
        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found")
        result = await self.check_candidate(candidate)
        await self.session.commit()
        return result

    async def bulk_check_candidates(
        self, ids: list[UUID], owner_id: UUID
    ) -> list[ProxyTestResult]:
        """Массовая проверка кандидатов (макс. BULK_CHECK_MAX)."""
        if len(ids) > BULK_CHECK_MAX:
            raise ValueError(f"Maximum {BULK_CHECK_MAX} candidates per bulk check")

        candidates: list[ProxyCandidate] = []
        for cid in ids:
            cand = await self.get_candidate(cid, owner_id)
            if cand:
                candidates.append(cand)

        if not candidates:
            return []

        sem = asyncio.Semaphore(settings.proxy_bulk_check_concurrency)

        async def check_with_sem(cand: ProxyCandidate) -> ProxyTestResult:
            async with sem:
                return await self.check_candidate(cand)

        tasks = [check_with_sem(c) for c in candidates]
        results = await asyncio.gather(*tasks)

        # Сохраняем результаты
        await self.session.commit()

        _LOGGER.info(
            "Bulk check completed",
            requested=len(ids),
            checked=len(candidates),
            working=sum(1 for r in results if r.is_working),
        )

        return list(results)

    # ================================================================== #
    #   APPROVE
    # ================================================================== #

    async def approve_candidate(
        self, candidate: ProxyCandidate, owner_id: UUID
    ) -> Proxy:
        """Одобрить кандидата и создать рабочий Proxy.

        Поддерживает все типы прокси:
        - socks5, http: создаёт обычный Proxy
        - mtproto: создаёт MTProto Proxy
        - local_adapter: создаёт Proxy с дополнительной метаинформацией

        Не создаёт дубликаты, если такой proxy уже существует.
        """
        if candidate.status not in ("alive", "new", "checking"):
            raise ValueError(
                f"Cannot approve candidate with status '{candidate.status}'. "
                "Only alive, new, or checking candidates can be approved."
            )

        # Проверка на дубликат рабочего proxy
        duplicate = await self._find_duplicate_proxy(
            host=candidate.host,
            port=candidate.port,
            secret=candidate.secret,
            owner_id=owner_id,
        )
        if duplicate:
            raise ValueError(
                f"Working proxy already exists for {candidate.host}:{candidate.port}"
            )

        # Определяем схему и тайтл
        scheme = candidate.proxy_type
        if scheme == "http" or scheme == "https":
            scheme = "http"
        elif scheme == "local_adapter":
            scheme = "socks5"  # local_adapter выставляет SOCKS5 endpoint

        title_parts = [scheme.upper(), candidate.host, str(candidate.port)]
        if candidate.source_name:
            title_parts.insert(0, candidate.source_name)
        title = " ".join(title_parts)

        # Создаём рабочий Proxy
        proxy = Proxy(
            owner_id=owner_id,
            title=title,
            scheme=scheme,
            host=candidate.host,
            port=candidate.port,
            username=candidate.username,
            password=candidate.password,
            secret=candidate.secret if candidate.proxy_type == "mtproto" else None,
            is_working=True if candidate.status == "alive" else None,
            ping_ms=candidate.latency_ms,
            last_checked_at=candidate.last_checked_at,
            status_message=f"Approved from candidate {candidate.id}",
            extra_data={
                "approved_from_candidate": str(candidate.id),
                "original_type": candidate.proxy_type,
                "source_type": candidate.source_type,
                "source_name": candidate.source_name,
            },
        )
        self.session.add(proxy)

        # Обновляем статус кандидата
        candidate.status = "approved"
        await self.session.commit()
        await self.session.refresh(proxy)

        _LOGGER.info(
            "Candidate approved, proxy created",
            candidate_id=str(candidate.id),
            proxy_id=str(proxy.id),
            host=proxy.host,
            port=proxy.port,
            scheme=proxy.scheme,
        )

        return proxy

    async def _find_duplicate_proxy(
        self,
        host: str,
        port: int,
        secret: str | None,
        owner_id: UUID,
    ) -> bool:
        """Проверить, существует ли рабочий proxy с такими host+port."""
        result = await self.session.execute(
            select(Proxy).where(
                Proxy.host == host,
                Proxy.port == port,
                Proxy.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none() is not None

    # ================================================================== #
    #   REJECT / DELETE
    # ================================================================== #

    async def reject_candidate(self, candidate: ProxyCandidate) -> None:
        """Отклонить кандидата (установить статус rejected)."""
        candidate.status = "rejected"
        await self.session.commit()
        _LOGGER.info("Candidate rejected", candidate_id=str(candidate.id))

    async def delete_candidate(self, candidate: ProxyCandidate) -> None:
        """Удалить кандидата."""
        await self.session.delete(candidate)
        await self.session.commit()
        _LOGGER.info("Candidate deleted", candidate_id=str(candidate.id))
