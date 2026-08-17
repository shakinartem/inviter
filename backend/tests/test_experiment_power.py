from __future__ import annotations

import unittest

from app.api.router import api_router
from app.features.experiments.power import ExperimentPowerPlanner


class ExperimentPowerContractTests(unittest.TestCase):
    def test_balanced_allocation_requires_less_total_sample_than_tiny_holdout(self) -> None:
        balanced = ExperimentPowerPlanner.required_total_units(
            baseline_rate=0.05,
            treatment_rate=0.07,
            holdout_fraction=0.50,
            alpha=0.05,
            power=0.80,
        )
        tiny_holdout = ExperimentPowerPlanner.required_total_units(
            baseline_rate=0.05,
            treatment_rate=0.07,
            holdout_fraction=0.10,
            alpha=0.05,
            power=0.80,
        )
        self.assertLess(balanced, tiny_holdout)

    def test_larger_lift_requires_less_sample(self) -> None:
        small_lift = ExperimentPowerPlanner.required_total_units(
            baseline_rate=0.05,
            treatment_rate=0.06,
            holdout_fraction=0.20,
        )
        large_lift = ExperimentPowerPlanner.required_total_units(
            baseline_rate=0.05,
            treatment_rate=0.08,
            holdout_fraction=0.20,
        )
        self.assertGreater(small_lift, large_lift)

    def test_more_units_reduce_minimum_detectable_effect(self) -> None:
        small = ExperimentPowerPlanner.minimum_detectable_effect(
            baseline_rate=0.05,
            treatment_units=800,
            holdout_units=200,
        )
        large = ExperimentPowerPlanner.minimum_detectable_effect(
            baseline_rate=0.05,
            treatment_units=4000,
            holdout_units=1000,
        )
        self.assertIsNotNone(small)
        self.assertIsNotNone(large)
        assert small is not None and large is not None
        self.assertLess(large, small)

    def test_power_route_is_registered_before_other_experiment_routes(self) -> None:
        paths = [getattr(route, "path", "") for route in api_router.routes]
        self.assertIn("/experiments/power-plan", paths)


if __name__ == "__main__":
    unittest.main()
