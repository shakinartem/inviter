from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.features.accounts.capacity import AccountCapacityRiskService
from app.features.accounts.models import Account


class AccountCapacityRiskTests(unittest.TestCase):
    def _account(self, **overrides):
        now = datetime.now(timezone.utc)
        values = {
            "label": "test-account",
            "platform": "telegram",
            "status": "active",
            "is_active": True,
            "health_score": 100.0,
            "created_at": now - timedelta(days=30),
        }
        values.update(overrides)
        return Account(**values)

    def test_target_errors_do_not_poison_account_health(self) -> None:
        now = datetime.now(timezone.utc)
        result = AccountCapacityRiskService.assess(
            self._account(),
            metrics={"attempts_24h": 20, "target_errors_24h": 15},
            campaign_daily_limit=40,
            now=now,
        )
        self.assertEqual(result.risk_score, 0.0)
        self.assertEqual(result.suggested_daily_capacity, 40)
        self.assertTrue(result.eligible)

    def test_flood_wait_reduces_capacity(self) -> None:
        now = datetime.now(timezone.utc)
        result = AccountCapacityRiskService.assess(
            self._account(),
            metrics={"attempts_24h": 10, "floodwaits_24h": 1, "account_errors_24h": 1},
            campaign_daily_limit=40,
            now=now,
        )
        self.assertGreater(result.risk_score, 0.0)
        self.assertLess(result.suggested_daily_capacity, 40)
        self.assertIn("recent_flood_wait", result.reasons)

    def test_active_cooldown_is_ineligible(self) -> None:
        now = datetime.now(timezone.utc)
        result = AccountCapacityRiskService.assess(
            self._account(status="cooldown", cooldown_until=now + timedelta(hours=1)),
            metrics={},
            campaign_daily_limit=40,
            now=now,
        )
        self.assertFalse(result.eligible)
        self.assertEqual(result.suggested_daily_capacity, 0)
        self.assertEqual(result.capacity_multiplier, 0.0)

    def test_new_account_never_exceeds_campaign_limit(self) -> None:
        now = datetime.now(timezone.utc)
        result = AccountCapacityRiskService.assess(
            self._account(created_at=now - timedelta(hours=12)),
            metrics={},
            campaign_daily_limit=50,
            now=now,
        )
        self.assertLessEqual(result.suggested_daily_capacity, 50)
        self.assertEqual(result.suggested_daily_capacity, 17)


if __name__ == "__main__":
    unittest.main()
