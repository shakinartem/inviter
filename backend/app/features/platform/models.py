"""
Platform models — перечисление платформ, их возможности и реестр.

Telegram — первый активный provider.
Остальные платформы добавлены как planned/not_implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PlatformType(str, Enum):
    """Поддерживаемые платформы."""
    TELEGRAM = "telegram"
    VK = "vk"
    WHATSAPP = "whatsapp"
    DISCORD = "discord"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    CUSTOM = "custom"


class PlatformStatus(str, Enum):
    """Статус реализации платформы."""
    ACTIVE = "active"
    PLANNED = "planned"
    DISABLED = "disabled"
    NOT_IMPLEMENTED = "not_implemented"


PLATFORM_STATUSES: tuple[str, ...] = tuple(s.value for s in PlatformStatus)


@dataclass
class PlatformCapabilities:
    """Возможности платформы."""
    platform: PlatformType
    display_name: str
    supports_proxy: bool
    supported_proxy_types: list[str]
    supports_invites: bool
    supports_messages: bool
    supports_group_sources: bool
    supports_member_parsing: bool
    status: PlatformStatus
    notes: str = ""


# ==================== Registry ====================

PLATFORM_REGISTRY: dict[PlatformType, PlatformCapabilities] = {
    PlatformType.TELEGRAM: PlatformCapabilities(
        platform=PlatformType.TELEGRAM,
        display_name="Telegram",
        supports_proxy=True,
        supported_proxy_types=["socks5", "http", "mtproto", "local_adapter"],
        supports_invites=True,
        supports_messages=True,
        supports_group_sources=True,
        supports_member_parsing=True,
        status=PlatformStatus.ACTIVE,
        notes="Полностью реализован: инвайтинг, парсинг, MTProto/SOCKS5/HTTP прокси.",
    ),
    PlatformType.VK: PlatformCapabilities(
        platform=PlatformType.VK,
        display_name="VK (Vkontakte)",
        supports_proxy=True,
        supported_proxy_types=["socks5", "http"],
        supports_invites=False,
        supports_messages=False,
        supports_group_sources=False,
        supports_member_parsing=False,
        status=PlatformStatus.PLANNED,
        notes="Архитектурная основа. Требует отдельной интеграции с соблюдением правил VK.",
    ),
    PlatformType.WHATSAPP: PlatformCapabilities(
        platform=PlatformType.WHATSAPP,
        display_name="WhatsApp",
        supports_proxy=True,
        supported_proxy_types=["socks5", "http"],
        supports_invites=False,
        supports_messages=False,
        supports_group_sources=False,
        supports_member_parsing=False,
        status=PlatformStatus.PLANNED,
        notes="Архитектурная основа. Требует отдельной интеграции с соблюдением правил WhatsApp.",
    ),
    PlatformType.DISCORD: PlatformCapabilities(
        platform=PlatformType.DISCORD,
        display_name="Discord",
        supports_proxy=True,
        supported_proxy_types=["socks5", "http"],
        supports_invites=False,
        supports_messages=False,
        supports_group_sources=False,
        supports_member_parsing=False,
        status=PlatformStatus.PLANNED,
        notes="Архитектурная основа. Требует отдельной интеграции с соблюдением правил Discord.",
    ),
    PlatformType.INSTAGRAM: PlatformCapabilities(
        platform=PlatformType.INSTAGRAM,
        display_name="Instagram",
        supports_proxy=True,
        supported_proxy_types=["socks5", "http"],
        supports_invites=False,
        supports_messages=False,
        supports_group_sources=False,
        supports_member_parsing=False,
        status=PlatformStatus.PLANNED,
        notes="Архитектурная основа. Требует отдельной интеграции с соблюдением правил Instagram.",
    ),
    PlatformType.FACEBOOK: PlatformCapabilities(
        platform=PlatformType.FACEBOOK,
        display_name="Facebook",
        supports_proxy=True,
        supported_proxy_types=["socks5", "http"],
        supports_invites=False,
        supports_messages=False,
        supports_group_sources=False,
        supports_member_parsing=False,
        status=PlatformStatus.PLANNED,
        notes="Архитектурная основа. Требует отдельной интеграции с соблюдением правил Facebook.",
    ),
    PlatformType.LINKEDIN: PlatformCapabilities(
        platform=PlatformType.LINKEDIN,
        display_name="LinkedIn",
        supports_proxy=True,
        supported_proxy_types=["socks5", "http"],
        supports_invites=False,
        supports_messages=False,
        supports_group_sources=False,
        supports_member_parsing=False,
        status=PlatformStatus.PLANNED,
        notes="Архитектурная основа. Требует отдельной интеграции с соблюдением правил LinkedIn.",
    ),
    PlatformType.CUSTOM: PlatformCapabilities(
        platform=PlatformType.CUSTOM,
        display_name="Custom",
        supports_proxy=True,
        supported_proxy_types=["socks5", "http"],
        supports_invites=False,
        supports_messages=False,
        supports_group_sources=False,
        supports_member_parsing=False,
        status=PlatformStatus.NOT_IMPLEMENTED,
        notes="Пользовательская интеграция. Не реализована.",
    ),
}


class PlatformRegistry:
    """Реестр платформ и их возможностей."""

    @staticmethod
    def get_capabilities(platform: PlatformType) -> Optional[PlatformCapabilities]:
        """Получить возможности платформы."""
        return PLATFORM_REGISTRY.get(platform)

    @staticmethod
    def get_all() -> list[PlatformCapabilities]:
        """Получить список всех платформ."""
        return list(PLATFORM_REGISTRY.values())

    @staticmethod
    def get_active() -> list[PlatformCapabilities]:
        """Получить только активные платформы."""
        return [
            p for p in PLATFORM_REGISTRY.values()
            if p.status == PlatformStatus.ACTIVE
        ]

    @staticmethod
    def get_planned() -> list[PlatformCapabilities]:
        """Получить запланированные платформы."""
        return [
            p for p in PLATFORM_REGISTRY.values()
            if p.status == PlatformStatus.PLANNED
        ]


def get_platform_capabilities(platform_str: str) -> Optional[PlatformCapabilities]:
    """Получить возможности платформы по строковому имени."""
    try:
        platform = PlatformType(platform_str)
    except ValueError:
        return None
    return PlatformRegistry.get_capabilities(platform)


def get_all_platforms() -> list[dict]:
    """Получить все платформы в формате для API."""
    return [
        {
            "platform": cap.platform.value,
            "display_name": cap.display_name,
            "supports_proxy": cap.supports_proxy,
            "supported_proxy_types": cap.supported_proxy_types,
            "supports_invites": cap.supports_invites,
            "supports_messages": cap.supports_messages,
            "supports_group_sources": cap.supports_group_sources,
            "supports_member_parsing": cap.supports_member_parsing,
            "status": cap.status.value,
            "notes": cap.notes,
        }
        for cap in PLATFORM_REGISTRY.values()
    ]