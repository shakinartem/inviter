from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.core.config import Settings


class ProductionConfigTests(unittest.TestCase):
    def test_production_rejects_default_app_secret(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(
                APP_ENV="production",
                APP_SECRET="change-me",
                POSTGRES_PASSWORD="postgres-password-long-enough",
                REDIS_PASSWORD="redis-password-long-enough",
            )

    def test_production_rejects_short_redis_password(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(
                APP_ENV="production",
                APP_SECRET="x" * 48,
                POSTGRES_PASSWORD="postgres-password-long-enough",
                REDIS_PASSWORD="short",
            )

    def test_production_accepts_strong_runtime_secrets(self) -> None:
        settings = Settings(
            APP_ENV="production",
            APP_SECRET="a" * 48,
            POSTGRES_PASSWORD="postgres-password-long-enough",
            REDIS_PASSWORD="redis-password-long-enough",
            APP_ALLOW_REGISTRATION=False,
            APP_DOCS_ENABLED=False,
            SESSIONS_DIR="/data/sessions",
        )
        self.assertFalse(settings.allow_registration)
        self.assertFalse(settings.docs_enabled)
        self.assertEqual(settings.sessions_dir, "/data/sessions")
        self.assertIn(":redis-password-long-enough@", settings.redis_url)

    def test_database_credentials_are_url_encoded(self) -> None:
        settings = Settings(
            POSTGRES_USER="user@example.com",
            POSTGRES_PASSWORD="p@ss:/word",
            POSTGRES_DB="db name",
        )
        self.assertIn("user%40example.com", settings.database_url)
        self.assertIn("p%40ss%3A%2Fword", settings.database_url)
        self.assertTrue(settings.database_url.endswith("/db%20name"))


if __name__ == "__main__":
    unittest.main()
