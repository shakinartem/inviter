"""
Platform adapter interface — абстракция для адаптеров инвайтинга разных платформ.

Telegram — первый активный provider с адаптером-обёрткой.
Остальные платформы — stub adapters, возвращающие NotImplemented.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from app.features.platform.models import (
    PlatformCapabilities,
    PlatformRegistry,
    PlatformStatus,
    PlatformType,
    get_platform_capabilities,
)


@dataclass
class PlatformInviteResult:
    """Результат попытки инвайта."""
    success: bool
    platform: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformCapabilitiesInfo:
    """Информация о возможностях платформы для API."""
    platform: str
    status: str
    capabilities: dict[str, bool | list[str] | str]


class PlatformInviteAdapter(ABC):
    """Абстрактный адаптер для инвайтинга на платформе.

    Все методы, кроме list_capabilities, могут выбрасывать NotImplementedError
    для платформ со статусом planned.
    """

    def __init__(self, platform: PlatformType):
        self.platform = platform
        caps = PlatformRegistry.get_capabilities(platform)
        self._capabilities = caps

    @abstractmethod
    def list_capabilities(self) -> PlatformCapabilitiesInfo:
        """Вернуть информацию о возможностях платформы."""
        ...

    async def validate_account(self, account_id: UUID) -> PlatformInviteResult:
        """Проверить аккаунт платформы."""
        raise NotImplementedError(
            f"validate_account not implemented for {self.platform.value}"
        )

    async def validate_proxy(self, proxy_id: UUID) -> PlatformInviteResult:
        """Проверить, подходит ли прокси для платформы."""
        raise NotImplementedError(
            f"validate_proxy not implemented for {self.platform.value}"
        )

    async def check_connection(self, account_id: UUID) -> PlatformInviteResult:
        """Проверить подключение к платформе."""
        raise NotImplementedError(
            f"check_connection not implemented for {self.platform.value}"
        )

    async def prepare_invite_job(self, **kwargs: Any) -> PlatformInviteResult:
        """Подготовить задачу инвайтинга."""
        raise NotImplementedError(
            f"prepare_invite_job not implemented for {self.platform.value}"
        )

    async def run_invite_attempt(self, **kwargs: Any) -> PlatformInviteResult:
        """Выполнить одну попытку инвайта."""
        raise NotImplementedError(
            f"run_invite_attempt not implemented for {self.platform.value}"
        )


class TelegramInviteAdapter(PlatformInviteAdapter):
    """Адаптер для Telegram (обёртка над существующей логикой).

    На данный момент возвращает capabilities и базовую проверку.
    Реальная логика инвайтинга уже реализована в inviter service.
    """

    def __init__(self) -> None:
        super().__init__(PlatformType.TELEGRAM)

    def list_capabilities(self) -> PlatformCapabilitiesInfo:
        caps = self._capabilities
        return PlatformCapabilitiesInfo(
            platform=self.platform.value,
            status=caps.status.value if caps else "unknown",
            capabilities={
                "supports_proxy": caps.supports_proxy if caps else False,
                "supported_proxy_types": caps.supported_proxy_types if caps else [],
                "supports_invites": caps.supports_invites if caps else False,
                "supports_messages": caps.supports_messages if caps else False,
                "supports_group_sources": caps.supports_group_sources if caps else False,
                "supports_member_parsing": caps.supports_member_parsing if caps else False,
            },
        )


class StubInviteAdapter(PlatformInviteAdapter):
    """Заглушка для плановых платформ.

    Все методы возвращают not_implemented или raising NotImplementedError.
    """

    def __init__(self, platform: PlatformType) -> None:
        super().__init__(platform)

    def list_capabilities(self) -> PlatformCapabilitiesInfo:
        caps = self._capabilities
        return PlatformCapabilitiesInfo(
            platform=self.platform.value,
            status=caps.status.value if caps else "not_implemented",
            capabilities={
                "supports_proxy": caps.supports_proxy if caps else False,
                "supported_proxy_types": caps.supported_proxy_types if caps else [],
                "supports_invites": False,
                "supports_messages": False,
                "supports_group_sources": False,
                "supports_member_parsing": False,
            },
        )


# ==================== Adapter factory ====================

_ADAPTER_REGISTRY: dict[PlatformType, type[PlatformInviteAdapter]] = {
    PlatformType.TELEGRAM: TelegramInviteAdapter,
    PlatformType.VK: StubInviteAdapter,
    PlatformType.WHATSAPP: StubInviteAdapter,
    PlatformType.DISCORD: StubInviteAdapter,
    PlatformType.INSTAGRAM: StubInviteAdapter,
    PlatformType.FACEBOOK: StubInviteAdapter,
    PlatformType.LINKEDIN: StubInviteAdapter,
    PlatformType.CUSTOM: StubInviteAdapter,
}


def get_adapter_for_platform(platform_str: str) -> Optional[PlatformInviteAdapter]:
    """Получить адаптер для платформы по строковому имени."""
    try:
        platform = PlatformType(platform_str)
    except ValueError:
        return None

    adapter_class = _ADAPTER_REGISTRY.get(platform)
    if adapter_class is None:
        return None

    if adapter_class == StubInviteAdapter:
        return StubInviteAdapter(platform)
    return adapter_class()