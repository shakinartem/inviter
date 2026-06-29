"""
Tests for platform foundation.
"""

from __future__ import annotations

import pytest
from app.features.platform.models import (
    PlatformType,
    PlatformStatus,
    PlatformRegistry,
    get_platform_capabilities,
    get_all_platforms,
)
from app.features.platform.adapter import (
    TelegramInviteAdapter,
    StubInviteAdapter,
    PlatformInviteAdapter,
    get_adapter_for_platform,
)


class TestPlatformModels:
    """Tests for platform models and registry."""

    def test_telegram_active(self):
        """Telegram should be active."""
        caps = PlatformRegistry.get_capabilities(PlatformType.TELEGRAM)
        assert caps is not None
        assert caps.status == PlatformStatus.ACTIVE
        assert caps.supports_invites is True
        assert caps.supports_proxy is True

    def test_planned_platforms_return_planned(self):
        """Planned platforms should return planned/not_implemented."""
        for pt in [
            PlatformType.VK,
            PlatformType.WHATSAPP,
            PlatformType.DISCORD,
            PlatformType.INSTAGRAM,
            PlatformType.FACEBOOK,
            PlatformType.LINKEDIN,
        ]:
            caps = PlatformRegistry.get_capabilities(pt)
            assert caps is not None
            assert caps.status == PlatformStatus.PLANNED
            assert caps.supports_invites is False

    def test_custom_not_implemented(self):
        """Custom should be not_implemented."""
        caps = PlatformRegistry.get_capabilities(PlatformType.CUSTOM)
        assert caps is not None
        assert caps.status == PlatformStatus.NOT_IMPLEMENTED

    def test_get_all_platforms_count(self):
        """get_all_platforms should return all platforms."""
        platforms = get_all_platforms()
        assert len(platforms) == 8  # All 8 platforms

    def test_get_platform_capabilities_by_string(self):
        """get_platform_capabilities by string."""
        caps = get_platform_capabilities("telegram")
        assert caps is not None
        assert caps.platform == PlatformType.TELEGRAM

        caps = get_platform_capabilities("vk")
        assert caps is not None
        assert caps.platform == PlatformType.VK

        caps = get_platform_capabilities("nonexistent")
        assert caps is None

    def test_telegram_supported_proxy_types(self):
        """Telegram should support socks5, http, mtproto, local_adapter."""
        caps = PlatformRegistry.get_capabilities(PlatformType.TELEGRAM)
        assert caps is not None
        proxy_types = caps.supported_proxy_types
        assert "socks5" in proxy_types
        assert "http" in proxy_types
        assert "mtproto" in proxy_types
        assert "local_adapter" in proxy_types


class TestPlatformAdapters:
    """Tests for platform adapters."""

    def test_telegram_adapter_list_capabilities(self):
        """Telegram adapter returns active capabilities."""
        adapter = TelegramInviteAdapter()
        caps = adapter.list_capabilities()
        assert caps.platform == "telegram"
        assert caps.status == "active"
        assert caps.capabilities["supports_invites"] is True

    def test_stub_adapter_returns_planned(self):
        """Stub adapter for planned platform returns planned status."""
        adapter = StubInviteAdapter(PlatformType.VK)
        caps = adapter.list_capabilities()
        assert caps.platform == "vk"
        assert caps.status == "planned"
        assert caps.capabilities["supports_invites"] is False

    def test_stub_adapter_raises_not_implemented(self):
        """Stub adapter methods raise NotImplementedError.""" 
        from uuid import uuid4
        adapter = StubInviteAdapter(PlatformType.WHATSAPP)
        # These methods should raise NotImplementedError
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with pytest.raises(NotImplementedError):
            loop.run_until_complete(adapter.validate_account(uuid4()))
        with pytest.raises(NotImplementedError):
            loop.run_until_complete(adapter.validate_proxy(uuid4()))
        with pytest.raises(NotImplementedError):
            loop.run_until_complete(adapter.check_connection(uuid4()))
        loop.close()

    def test_get_adapter_for_platform(self):
        """get_adapter_for_platform returns correct adapter."""
        tg_adapter = get_adapter_for_platform("telegram")
        assert tg_adapter is not None
        assert isinstance(tg_adapter, TelegramInviteAdapter)

        vk_adapter = get_adapter_for_platform("vk")
        assert vk_adapter is not None
        assert isinstance(vk_adapter, StubInviteAdapter)

        nonexistent = get_adapter_for_platform("nonexistent")
        assert nonexistent is None

    def test_unsupported_adapter_action_returns_safe_not_implemented(self):
        """Unsupported adapter action returns safe NotImplemented, not crash."""
        from uuid import uuid4

        adapter = StubInviteAdapter(PlatformType.DISCORD)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # These should raise NotImplementedError with descriptive messages
        try:
            loop.run_until_complete(adapter.validate_account(uuid4()))
            assert False, "Should have raised"
        except NotImplementedError as e:
            assert "not implemented" in str(e).lower()
            assert "discord" in str(e).lower()
        loop.close()
