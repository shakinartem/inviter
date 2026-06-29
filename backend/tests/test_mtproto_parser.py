"""Unit-тесты для парсера MTProto-ссылок."""

from __future__ import annotations

import unittest

from app.features.proxies.mtproto_parser import (
    find_mtproto_urls,
    normalize_mtproto_item,
    parse_mtproto_text,
    parse_mtproto_url,
)


class TestFindMtprotoUrls(unittest.TestCase):
    """Тесты для find_mtproto_urls."""

    def test_find_tg_proto(self):
        """Поиск tg://proxy? ссылки."""
        text = "tg://proxy?server=1.2.3.4&port=443&secret=abc123"
        urls = find_mtproto_urls(text)
        self.assertEqual(len(urls), 1)
        self.assertIn("tg://proxy?server=1.2.3.4&port=443&secret=abc123", urls)

    def test_find_https_tme(self):
        """Поиск https://t.me/proxy? ссылки."""
        text = "https://t.me/proxy?server=example.com&port=443&secret=abc123"
        urls = find_mtproto_urls(text)
        self.assertEqual(len(urls), 1)
        self.assertIn("https://t.me/proxy?server=example.com&port=443&secret=abc123", urls)

    def test_find_http_tme(self):
        """Поиск http://t.me/proxy? ссылки."""
        text = "http://t.me/proxy?server=example.com&port=443&secret=abc123"
        urls = find_mtproto_urls(text)
        self.assertEqual(len(urls), 1)

    def test_find_bare_tme(self):
        """Поиск t.me/proxy? ссылки без протокола."""
        text = "t.me/proxy?server=example.com&port=443&secret=abc123"
        urls = find_mtproto_urls(text)
        self.assertEqual(len(urls), 1)

    def test_find_multiple_urls(self):
        """Поиск нескольких ссылок в тексте."""
        text = (
            "tg://proxy?server=1.2.3.4&port=443&secret=abc\n"
            "https://t.me/proxy?server=5.6.7.8&port=1080&secret=xyz\n"
            "Some garbage text"
        )
        urls = find_mtproto_urls(text)
        self.assertEqual(len(urls), 2)

    def test_ignore_garbage(self):
        """Не крашится на мусоре."""
        text = "Some random text without any proxy links"
        urls = find_mtproto_urls(text)
        self.assertEqual(len(urls), 0)

    def test_deduplicate(self):
        """Не добавляет дубликаты ссылок."""
        text = (
            "tg://proxy?server=1.2.3.4&port=443&secret=abc\n"
            "tg://proxy?server=1.2.3.4&port=443&secret=abc"
        )
        urls = find_mtproto_urls(text)
        self.assertEqual(len(urls), 1)


class TestParseMtprotoUrl(unittest.TestCase):
    """Тесты для parse_mtproto_url."""

    def test_parse_tg_proto(self):
        """Парсинг tg://proxy?server=1.2.3.4&port=443&secret=abcdef."""
        url = "tg://proxy?server=1.2.3.4&port=443&secret=abcdef"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertTrue(item.is_valid)
        self.assertEqual(item.host, "1.2.3.4")
        self.assertEqual(item.port, 443)
        self.assertEqual(item.secret, "abcdef")
        self.assertEqual(item.raw_url, url)

    def test_parse_https_tme(self):
        """Парсинг https://t.me/proxy?server=example.com&port=443&secret=abcdef."""
        url = "https://t.me/proxy?server=example.com&port=443&secret=abcdef"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertTrue(item.is_valid)
        self.assertEqual(item.host, "example.com")
        self.assertEqual(item.port, 443)
        self.assertEqual(item.secret, "abcdef")

    def test_parse_reordered_params(self):
        """Парсинг с параметрами в другом порядке."""
        url = "tg://proxy?port=8080&secret=xyz789&server=10.0.0.1"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertTrue(item.is_valid)
        self.assertEqual(item.host, "10.0.0.1")
        self.assertEqual(item.port, 8080)
        self.assertEqual(item.secret, "xyz789")

    def test_parse_host_alias(self):
        """Парсинг с 'host' вместо 'server'."""
        url = "tg://proxy?host=1.2.3.4&port=443&secret=abc"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertTrue(item.is_valid)
        self.assertEqual(item.host, "1.2.3.4")
        self.assertEqual(item.port, 443)

    def test_invalid_port_zero(self):
        """Игнорировать порт 0."""
        url = "tg://proxy?server=1.2.3.4&port=0&secret=abc"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertFalse(item.is_valid)

    def test_invalid_port_negative(self):
        """Игнорировать отрицательный порт."""
        url = "tg://proxy?server=1.2.3.4&port=-1&secret=abc"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertFalse(item.is_valid)

    def test_invalid_port_over_65535(self):
        """Игнорировать порт > 65535."""
        url = "tg://proxy?server=1.2.3.4&port=70000&secret=abc"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertFalse(item.is_valid)

    def test_invalid_port_non_numeric(self):
        """Игнорировать нечисловой порт."""
        url = "tg://proxy?server=1.2.3.4&port=abc&secret=def"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertFalse(item.is_valid)

    def test_missing_secret(self):
        """Игнорировать отсутствующий secret."""
        url = "tg://proxy?server=1.2.3.4&port=443"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertFalse(item.is_valid)

    def test_missing_host(self):
        """Игнорировать отсутствующий host."""
        url = "tg://proxy?port=443&secret=abc"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertFalse(item.is_valid)

    def test_missing_port(self):
        """Игнорировать отсутствующий port."""
        url = "tg://proxy?server=1.2.3.4&secret=abc"
        item = parse_mtproto_url(url)
        self.assertIsNotNone(item)
        self.assertFalse(item.is_valid)


class TestNormalizeMtprotoItem(unittest.TestCase):
    """Тесты для normalize_mtproto_item."""

    def test_normalize(self):
        """Нормализация возвращает (host, port, secret)."""
        item = parse_mtproto_url("tg://proxy?server=1.2.3.4&port=443&secret=abc")
        key = normalize_mtproto_item(item)
        self.assertEqual(key, ("1.2.3.4", 443, "abc"))


class TestParseMtprotoText(unittest.TestCase):
    """Тесты для parse_mtproto_text."""

    def test_parse_multiple_links(self):
        """Парсинг нескольких ссылок в тексте."""
        text = (
            "tg://proxy?server=1.2.3.4&port=443&secret=abc\n"
            "https://t.me/proxy?server=5.6.7.8&port=1080&secret=xyz"
        )
        result = parse_mtproto_text(text)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(len(result.errors), 0)

    def test_parse_with_invalid_links(self):
        """Парсинг с некорректными ссылками."""
        text = (
            "tg://proxy?server=1.2.3.4&port=443&secret=abc\n"
            "tg://proxy?server=5.6.7.8&port=99999&secret=xyz"
        )
        result = parse_mtproto_text(text)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(len(result.errors), 1)

    def test_parse_with_garbage(self):
        """Парсинг текста с мусором."""
        text = (
            "Some text before\n"
            "tg://proxy?server=1.2.3.4&port=443&secret=abc\n"
            "Some text after\n"
            "Random stuff here"
        )
        result = parse_mtproto_text(text)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(len(result.errors), 0)

    def test_empty_text(self):
        """Пустой текст."""
        result = parse_mtproto_text("")
        self.assertEqual(len(result.items), 0)

    def test_only_garbage(self):
        """Только мусор."""
        result = parse_mtproto_text("Just some random text without links")
        self.assertEqual(len(result.items), 0)

    def test_deduplicate_same_proxy(self):
        """Две одинаковые ссылки — один результат."""
        text = (
            "tg://proxy?server=1.2.3.4&port=443&secret=abc\n"
            "tg://proxy?server=1.2.3.4&port=443&secret=abc"
        )
        result = parse_mtproto_text(text)
        self.assertEqual(len(result.items), 1)

    def test_parse_official_server_port_secret_format(self):
        text = """
        Server: proxy.example.com
        Port: 443
        Secret: abcdef123456
        """
        result = parse_mtproto_text(text)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].host, "proxy.example.com")
        self.assertEqual(result.items[0].port, 443)
        self.assertEqual(result.items[0].secret, "abcdef123456")


if __name__ == "__main__":
    unittest.main()
