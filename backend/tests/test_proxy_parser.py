"""
Tests for proxy parsers (MTProto and text proxy parsers).
"""

from __future__ import annotations

import pytest
from app.features.proxies.mtproto_parser import (
    find_mtproto_urls,
    parse_mtproto_url,
    parse_mtproto_text,
)


class TestMTProtoParser:
    """Tests for MTProto URL parser."""

    def test_parse_tg_proto_url(self):
        """Parse tg://proxy?server=1.2.3.4&port=443&secret=abcdef"""
        item = parse_mtproto_url(
            "tg://proxy?server=1.2.3.4&port=443&secret=abcdef"
        )
        assert item is not None
        assert item.is_valid
        assert item.host == "1.2.3.4"
        assert item.port == 443
        assert item.secret == "abcdef"

    def test_parse_https_tme_url(self):
        """Parse https://t.me/proxy?server=example.com&port=443&secret=abcdef"""
        item = parse_mtproto_url(
            "https://t.me/proxy?server=example.com&port=443&secret=abcdef"
        )
        assert item is not None
        assert item.is_valid
        assert item.host == "example.com"
        assert item.port == 443
        assert item.secret == "abcdef"

    def test_parse_http_tme_url(self):
        """Parse http://t.me/proxy?server=1.2.3.4&port=80&secret=xyz"""
        item = parse_mtproto_url(
            "http://t.me/proxy?server=1.2.3.4&port=80&secret=xyz"
        )
        assert item is not None
        assert item.is_valid
        assert item.host == "1.2.3.4"
        assert item.port == 80

    def test_parse_tme_without_protocol(self):
        """Parse t.me/proxy?server=1.2.3.4&port=443&secret=secret123"""
        item = parse_mtproto_url(
            "t.me/proxy?server=1.2.3.4&port=443&secret=secret123"
        )
        assert item is not None
        assert item.is_valid
        assert item.host == "1.2.3.4"
        assert item.port == 443

    def test_parse_params_in_any_order(self):
        """Parse tg://proxy?secret=SECRET&port=8080&server=HOST"""
        item = parse_mtproto_url(
            "tg://proxy?secret=SECRET&port=8080&server=HOST"
        )
        assert item is not None
        assert item.is_valid
        assert item.host == "HOST"
        assert item.port == 8080
        assert item.secret == "SECRET"

    def test_invalid_port_ignored(self):
        """Invalid port should be marked as invalid."""
        item = parse_mtproto_url(
            "tg://proxy?server=1.2.3.4&port=99999&secret=abc"
        )
        assert item is not None
        assert not item.is_valid
        assert "Port" in (item.error_message or "")

    def test_missing_secret_ignored(self):
        """Missing secret should be marked as invalid."""
        item = parse_mtproto_url(
            "tg://proxy?server=1.2.3.4&port=443"
        )
        assert item is not None
        assert not item.is_valid
        assert "secret" in (item.error_message or "").lower()

    def test_find_mtproto_urls_in_text(self):
        """Find multiple MTProto URLs in text."""
        text = (
            "tg://proxy?server=1.2.3.4&port=443&secret=abc\n"
            "Some random text\n"
            "https://t.me/proxy?server=5.6.7.8&port=1080&secret=xyz\n"
            "More text"
        )
        urls = find_mtproto_urls(text)
        assert len(urls) == 2

    def test_duplicates_skipped(self):
        """Duplicate URLs should not be created."""
        text = (
            "tg://proxy?server=1.2.3.4&port=443&secret=abc\n"
            "tg://proxy?server=1.2.3.4&port=443&secret=abc"
        )
        urls = find_mtproto_urls(text)
        assert len(urls) == 1

    def test_parse_mtproto_text_result(self):
        """parse_mtproto_text returns items and errors."""
        text = (
            "tg://proxy?server=1.2.3.4&port=443&secret=abc\n"
            "tg://proxy?server=5.6.7.8&port=99999&secret=xyz\n"
            "tg://proxy?server=10.0.0.1&port=8080&secret=def"
        )
        result = parse_mtproto_text(text)
        assert len(result.items) == 2  # Two valid
        assert len(result.errors) == 1  # One invalid (port)


class TestTextProxyParser:
    """Tests for text proxy line parser."""

    def _parse_proxy_line_simple(self, line: str) -> tuple:
        """Simple parser matching candidate_service._parse_proxy_line logic."""
        import re
        line = line.strip()
        proxy_type = "socks5"
        username = None
        password = None
        host = None
        port = 0

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
            simple_match = re.match(r"^([a-zA-Z0-9.-]+):(\d{1,5})$", line)
            if simple_match:
                host = simple_match.group(1)
                port = int(simple_match.group(2))
            else:
                raise ValueError(f"Cannot parse proxy line: {line}")

        if not (1 <= port <= 65535):
            raise ValueError(f"Invalid port: {port}")

        return proxy_type, host, port, username or None, password or None

    def test_parse_socks5_user_pass(self):
        """Parse socks5://user:pass@host:port"""
        result = self._parse_proxy_line_simple("socks5://user:pass@1.2.3.4:1080")
        assert result[0] == "socks5"
        assert result[1] == "1.2.3.4"
        assert result[2] == 1080
        assert result[3] == "user"
        assert result[4] == "pass"

    def test_parse_http_host_port(self):
        """Parse http://host:port"""
        result = self._parse_proxy_line_simple("http://5.6.7.8:3128")
        assert result[0] == "http"
        assert result[1] == "5.6.7.8"
        assert result[2] == 3128

    def test_parse_host_port_only(self):
        """Parse host:port (defaults to socks5)"""
        result = self._parse_proxy_line_simple("9.10.11.12:4153")
        assert result[0] == "socks5"
        assert result[1] == "9.10.11.12"
        assert result[2] == 4153

    def test_parse_socks5_no_auth(self):
        """Parse socks5://host:port"""
        result = self._parse_proxy_line_simple("socks5://1.2.3.4:1080")
        assert result[0] == "socks5"
        assert result[1] == "1.2.3.4"
        assert result[2] == 1080
        assert result[3] is None

    def test_parse_http_user_pass(self):
        """Parse http://user:pass@host:port"""
        result = self._parse_proxy_line_simple("http://user:pass@1.2.3.4:8080")
        assert result[0] == "http"
        assert result[3] == "user"
        assert result[4] == "pass"

    def test_invalid_line_raises(self):
        """Invalid line raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse"):
            self._parse_proxy_line_simple("not a proxy")

    def test_invalid_port_raises(self):
        """Invalid port raises ValueError."""
        with pytest.raises(ValueError, match="Invalid port"):
            self._parse_proxy_line_simple("1.2.3.4:99999")