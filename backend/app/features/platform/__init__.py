"""
Platform Foundation — архитектурная основа для поддержки нескольких мессенджеров/соцсетей.

Telegram — первый активный provider.
Остальные платформы добавлены как planned/not_implemented.
"""

from app.features.platform.models import (
    PLATFORM_STATUSES,
    PlatformStatus,
    PlatformType,
    PlatformCapabilities,
    PlatformRegistry,
    get_platform_capabilities,
    get_all_platforms,
)
from app.features.platform.adapter import (
    PlatformInviteAdapter,
    PlatformInviteResult,
    PlatformCapabilitiesInfo,
    TelegramInviteAdapter,
    StubInviteAdapter,
    get_adapter_for_platform,
)

__all__ = (
    "PlatformStatus",
    "PlatformType",
    "PlatformCapabilities",
    "PlatformRegistry",
    "get_platform_capabilities",
    "get_all_platforms",
    "PLATFORM_STATUSES",
    "PlatformInviteAdapter",
    "PlatformInviteResult",
    "PlatformCapabilitiesInfo",
    "TelegramInviteAdapter",
    "StubInviteAdapter",
    "get_adapter_for_platform",
)