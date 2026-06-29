"""
Парсер MTProto-прокси ссылок.

Поддерживаемые форматы:
- tg://proxy?server=HOST&port=PORT&secret=SECRET
- https://t.me/proxy?server=HOST&port=PORT&secret=SECRET
- http://t.me/proxy?server=HOST&port=PORT&secret=SECRET
- t.me/proxy?server=HOST&port=PORT&secret=SECRET

Параметры могут быть в любом порядке.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import parse_qs, urlparse


@dataclass
class ParsedMtprotoItem:
    """Результат парсинга одной MTProto-ссылки."""
    host: str
    port: int
    secret: str
    raw_url: str
    is_valid: bool = True
    error_message: str | None = None


@dataclass
class MtprotoParseResult:
    """Результат парсинга текста с MTProto-ссылками."""
    items: list[ParsedMtprotoItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Регулярка для поиска MTProto-ссылок в тексте
# Ищет: tg://proxy?... или t.me/proxy?... (с опциональными http/https)
MTPROTO_URL_PATTERN = re.compile(
    r'(?:https?://)?'
    r'(?:t\.me|telegram\.me|telegram\.dog)'
    r'/proxy\?[^\s<>"\'\)]+',
    re.IGNORECASE,
)

TG_PROTO_PATTERN = re.compile(
    r'tg://proxy\?[^\s<>"\'\)]+',
    re.IGNORECASE,
)

OFFICIAL_BLOCK_PATTERN = re.compile(
    r"Server:\s*(?P<host>[^\s\r\n]+)\s+"
    r"Port:\s*(?P<port>\d{1,5})\s+"
    r"Secret:\s*(?P<secret>[0-9a-fA-F]+)",
    re.IGNORECASE,
)


def parse_mtproto_url(url: str) -> ParsedMtprotoItem | None:
    """Распарсить одну MTProto-ссылку.

    Возвращает ParsedMtprotoItem с полями host, port, secret, raw_url.
    Если ссылка некорректна — возвращает item с is_valid=False и error_message.
    """
    raw_url = url.strip()

    # Нормализуем tg:// ссылки для парсинга query-параметров
    if raw_url.startswith("tg://"):
        # Заменяем tg://proxy? на http://proxy? для urlparse
        query_part = raw_url.replace("tg://proxy", "").lstrip("?")
        params = parse_qs(query_part, keep_blank_values=True)
    else:
        # Для t.me ссылок используем urlparse
        parsed = urlparse(raw_url)
        params = parse_qs(parsed.query, keep_blank_values=True)

    # Извлекаем параметры
    host = _get_param(params, "server") or _get_param(params, "host")
    port_str = _get_param(params, "port")
    secret = _get_param(params, "secret")

    # Валидация
    if not host:
        return ParsedMtprotoItem(
            host="", port=0, secret="", raw_url=raw_url,
            is_valid=False, error_message="Missing server/host parameter",
        )

    if not port_str:
        return ParsedMtprotoItem(
            host=host, port=0, secret=secret or "", raw_url=raw_url,
            is_valid=False, error_message="Missing port parameter",
        )

    try:
        port = int(port_str)
    except (ValueError, TypeError):
        return ParsedMtprotoItem(
            host=host, port=0, secret=secret or "", raw_url=raw_url,
            is_valid=False, error_message=f"Invalid port: {port_str}",
        )

    if not (1 <= port <= 65535):
        return ParsedMtprotoItem(
            host=host, port=port, secret=secret or "", raw_url=raw_url,
            is_valid=False, error_message=f"Port out of range (1-65535): {port}",
        )

    if not secret:
        return ParsedMtprotoItem(
            host=host, port=port, secret="", raw_url=raw_url,
            is_valid=False, error_message="Missing secret parameter",
        )

    return ParsedMtprotoItem(
        host=host,
        port=port,
        secret=secret,
        raw_url=raw_url,
        is_valid=True,
    )


def _get_param(params: dict, name: str) -> str | None:
    """Получить первый элемент параметра query."""
    values = params.get(name)
    if values and len(values) > 0 and values[0].strip():
        return values[0].strip()
    return None


def find_mtproto_urls(text: str) -> list[str]:
    """Найти все MTProto-ссылки в тексте.

    Ищет оба формата: tg://proxy?... и t.me/proxy?...
    """
    found: list[str] = []
    # Ищем t.me формат
    for match in MTPROTO_URL_PATTERN.finditer(text):
        url = match.group(0).strip()
        if url not in found:
            found.append(url)
    # Ищем tg:// формат
    for match in TG_PROTO_PATTERN.finditer(text):
        url = match.group(0).strip()
        if url not in found:
            found.append(url)
    return found


def parse_mtproto_text(text: str) -> MtprotoParseResult:
    """Распарсить текст и извлечь все MTProto-прокси.

    Args:
        text: Текст для парсинга.

    Returns:
        MtprotoParseResult со списком найденных прокси и ошибок.
    """
    result = MtprotoParseResult()
    urls = find_mtproto_urls(text)
    seen: set[tuple[str, int, str]] = set()

    for url in urls:
        item = parse_mtproto_url(url)
        if item is None:
            continue
        if item.is_valid:
            key = normalize_mtproto_item(item)
            if key not in seen:
                seen.add(key)
                result.items.append(item)
        else:
            result.errors.append(
                f"Invalid proxy in '{url[:80]}': {item.error_message}"
            )

    for match in OFFICIAL_BLOCK_PATTERN.finditer(text):
        host = match.group("host").strip()
        port = int(match.group("port"))
        secret = match.group("secret").strip()
        raw = match.group(0)
        if not (1 <= port <= 65535):
            result.errors.append(
                f"Invalid proxy in '{raw[:80]}': Port out of range (1-65535): {port}"
            )
            continue
        item = ParsedMtprotoItem(host=host, port=port, secret=secret, raw_url=raw)
        key = normalize_mtproto_item(item)
        if key not in seen:
            seen.add(key)
            result.items.append(item)

    return result


def normalize_mtproto_item(item: ParsedMtprotoItem) -> tuple[str, int, str]:
    """Нормализовать MTProto-прокси для дедупликации.

    Возвращает (host, port, secret).
    """
    return (item.host, item.port, item.secret)
