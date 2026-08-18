from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.features.inviter.schemas import InviteSettings
from app.features.orchestration.resilience import summarize_resilience_capacities


class ExecutionResilienceTests(unittest.TestCase):
    def test_zero_reserve_is_not_n_minus_one_ready_for_three_equal_accounts(self) -> None:
        summary = summarize_resilience_capacities([30, 30, 30], 0)
        self.assertEqual(summary.normal_daily_capacity, 90)
        self.assertEqual(summary.emergency_daily_capacity, 90)
        self.assertEqual(summary.n_minus_one_surviving_capacity, 60)
        self.assertEqual(summary.n_minus_one_margin, -30)
        self.assertFalse(summary.n_minus_one_covered)
        self.assertEqual(summary.recommended_min_reserve_percentage, 34.0)

    def test_sufficient_reserve_covers_largest_account_loss(self) -> None:
        summary = summarize_resilience_capacities([30, 30, 30], 34)
        self.assertEqual(summary.normal_capacities, (19, 19, 19))
        self.assertEqual(summary.normal_daily_capacity, 57)
        self.assertEqual(summary.n_minus_one_surviving_capacity, 60)
        self.assertEqual(summary.n_minus_one_margin, 3)
        self.assertTrue(summary.n_minus_one_covered)
        self.assertGreater(summary.resilience_ratio, 1.0)

    def test_concentrated_pool_needs_more_than_practical_reserve(self) -> None:
        summary = summarize_resilience_capacities([80, 20], 50)
        self.assertEqual(summary.recommended_min_reserve_percentage, 50.0)
        self.assertFalse(summary.n_minus_one_covered)
        self.assertLess(summary.n_minus_one_margin, 0)

    def test_single_account_is_always_single_point_of_failure(self) -> None:
        summary = summarize_resilience_capacities([30], 50)
        self.assertFalse(summary.n_minus_one_covered)
        self.assertEqual(summary.n_minus_one_surviving_capacity, 0)
        self.assertIsNone(summary.recommended_min_reserve_percentage)

    def test_reserve_is_explicit_and_bounded(self) -> None:
        self.assertEqual(InviteSettings().reserve_capacity_percentage, 0.0)
        with self.assertRaises(ValidationError):
            InviteSettings(reserve_capacity_percentage=51)
        with self.assertRaises(ValidationError):
            InviteSettings(reserve_capacity_percentage=-1)


if __name__ == "__main__":
    unittest.main()
