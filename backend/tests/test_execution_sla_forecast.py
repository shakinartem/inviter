from __future__ import annotations

import unittest

from app.features.orchestration.sla import (
    conservative_daily_hazard,
    normal_capacity,
    pool_evidence_quality,
    posterior_daily_hazard,
    simulate_sla_scenarios,
)


class ExecutionSLAForecastTests(unittest.TestCase):
    def test_no_history_uses_nonzero_prior(self) -> None:
        self.assertAlmostEqual(posterior_daily_hazard(hard_failure_days=0, exposure_days=0), 0.05)
        self.assertLess(
            posterior_daily_hazard(hard_failure_days=0, exposure_days=30),
            0.05,
        )

    def test_conservative_hazard_is_not_below_posterior(self) -> None:
        posterior = posterior_daily_hazard(hard_failure_days=1, exposure_days=20)
        conservative = conservative_daily_hazard(hard_failure_days=1, exposure_days=20)
        self.assertGreaterEqual(conservative, posterior)

    def test_reserve_can_preserve_schedule_continuity_after_account_loss(self) -> None:
        # Account 1 is unavailable for the whole one-day scenario. Without
        # reserve the committed rate is 90/day and only 60 survives. With 34%
        # reserve the committed rate is 57/day, which the two survivors cover.
        result = simulate_sla_scenarios(
            emergency_capacities=[30, 30, 30],
            hazards=[1.0, 0.0, 0.0],
            reserve_percentages=[0.0, 34.0],
            remaining_actions=50,
            deadline_days=1,
            simulations=500,
            seed=7,
        )
        zero_continuity, zero_completion, _ = result[0.0]
        reserve_continuity, reserve_completion, _ = result[34.0]
        self.assertEqual(zero_continuity, 0.0)
        self.assertEqual(reserve_continuity, 1.0)
        self.assertEqual(zero_completion, 1.0)
        self.assertEqual(reserve_completion, 1.0)

    def test_too_much_reserve_can_make_fixed_workload_infeasible(self) -> None:
        result = simulate_sla_scenarios(
            emergency_capacities=[30, 30, 30],
            hazards=[0.0, 0.0, 0.0],
            reserve_percentages=[0.0, 50.0],
            remaining_actions=100,
            deadline_days=2,
            simulations=500,
            seed=11,
        )
        self.assertEqual(result[0.0][1], 1.0)
        self.assertEqual(result[50.0][1], 0.0)
        self.assertEqual(normal_capacity(30, 50), 15)

    def test_pool_evidence_requires_repeated_account_exposure(self) -> None:
        self.assertEqual(pool_evidence_quality([0, 0, 0]), "limited")
        self.assertEqual(pool_evidence_quality([10, 10, 10]), "usable")
        self.assertEqual(pool_evidence_quality([20, 20, 20]), "strong")


if __name__ == "__main__":
    unittest.main()
