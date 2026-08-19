from __future__ import annotations

import unittest

from app.features.orchestration.preflight_math import recommend_preflight_budget


class PreflightBudgetRecommendationTests(unittest.TestCase):
    def test_cohort_shortfall_uses_executable_workload_for_required_rate(self) -> None:
        result = recommend_preflight_budget(
            requested_actions=1000,
            executable_actions=600,
            normal_daily_capacity=100,
            deadline_days=7,
        )
        self.assertEqual(result.required_daily_rate, 86)
        self.assertEqual(result.maximum_safe_action_budget, 600)
        self.assertEqual(result.recommended_action_budget, 600)
        self.assertEqual(result.recommended_deadline_days, 6)
        self.assertTrue(result.budget_reduction_needed)
        self.assertFalse(result.deadline_extension_needed)

    def test_capacity_shortfall_recommends_budget_or_longer_deadline(self) -> None:
        result = recommend_preflight_budget(
            requested_actions=1000,
            executable_actions=1000,
            normal_daily_capacity=100,
            deadline_days=7,
        )
        self.assertEqual(result.required_daily_rate, 143)
        self.assertEqual(result.maximum_safe_action_budget, 700)
        self.assertEqual(result.recommended_action_budget, 700)
        self.assertEqual(result.recommended_deadline_days, 10)
        self.assertTrue(result.budget_reduction_needed)
        self.assertTrue(result.deadline_extension_needed)

    def test_feasible_workload_keeps_requested_budget(self) -> None:
        result = recommend_preflight_budget(
            requested_actions=500,
            executable_actions=500,
            normal_daily_capacity=100,
            deadline_days=7,
        )
        self.assertEqual(result.required_daily_rate, 72)
        self.assertEqual(result.maximum_safe_action_budget, 500)
        self.assertEqual(result.recommended_action_budget, 500)
        self.assertEqual(result.recommended_deadline_days, 5)
        self.assertFalse(result.budget_reduction_needed)
        self.assertFalse(result.deadline_extension_needed)

    def test_zero_safe_capacity_recommends_zero_budget(self) -> None:
        result = recommend_preflight_budget(
            requested_actions=100,
            executable_actions=100,
            normal_daily_capacity=0,
            deadline_days=7,
        )
        self.assertEqual(result.maximum_safe_action_budget, 0)
        self.assertEqual(result.recommended_action_budget, 0)
        self.assertIsNone(result.recommended_deadline_days)
        self.assertTrue(result.budget_reduction_needed)


if __name__ == "__main__":
    unittest.main()
