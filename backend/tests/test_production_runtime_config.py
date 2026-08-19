import unittest

from pydantic import ValidationError

from app.core.config import Settings


SAFE = {
    "APP_ENV": "production",
    "APP_DEBUG": False,
    "APP_SECRET": "a" * 64,
    "POSTGRES_PASSWORD": "b" * 32,
    "REDIS_PASSWORD": "c" * 32,
    "APP_ALLOWED_HOSTS": "inviter.example.test,127.0.0.1,backend",
    "APP_CORS_ORIGINS": "https://inviter.example.test",
    "APP_ALLOW_REGISTRATION": False,
    "APP_DOCS_ENABLED": False,
}


class ProductionRuntimeConfigTests(unittest.TestCase):
    def test_safe_production_settings_are_accepted(self):
        settings = Settings(**SAFE)
        self.assertEqual(settings.environment, "production")
        self.assertFalse(settings.debug)

    def test_template_secret_is_rejected_even_when_long(self):
        values = dict(SAFE)
        values["APP_SECRET"] = "CHANGE_ME_64_PLUS_RANDOM_CHARACTERS___________"
        with self.assertRaises(ValidationError):
            Settings(**values)

    def test_wildcard_allowed_host_is_rejected(self):
        values = dict(SAFE)
        values["APP_ALLOWED_HOSTS"] = "*"
        with self.assertRaises(ValidationError):
            Settings(**values)

    def test_wildcard_cors_is_rejected(self):
        values = dict(SAFE)
        values["APP_CORS_ORIGINS"] = "*"
        with self.assertRaises(ValidationError):
            Settings(**values)

    def test_debug_is_rejected_in_production(self):
        values = dict(SAFE)
        values["APP_DEBUG"] = True
        with self.assertRaises(ValidationError):
            Settings(**values)


if __name__ == "__main__":
    unittest.main()
