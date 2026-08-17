from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.features.allocations.frontier_schemas import CapacityFrontierRequest


class CapacityEconomicsFrontierContractTests(unittest.TestCase):
    def test_capacities_are_sorted_and_deduplicated(self) -> None:
        payload = CapacityFrontierRequest.model_validate({
            "capacities": [1000, 100, 500, 100, 500],
            "value_unit": "rub",
        })
        self.assertEqual(payload.capacities, [100, 500, 1000])
        self.assertEqual(payload.value_unit, "RUB")

    def test_outcome_frontier_rejects_action_cost(self) -> None:
        with self.assertRaises(ValidationError):
            CapacityFrontierRequest.model_validate({
                "objective": "incremental_outcomes",
                "value_unit": None,
                "value_aggregation": None,
                "event_type": "converted",
                "cost_per_action": 100.0,
            })

    def test_business_value_frontier_requires_unit(self) -> None:
        with self.assertRaises(ValidationError):
            CapacityFrontierRequest.model_validate({
                "objective": "incremental_business_value",
                "value_unit": None,
            })

    def test_capacity_bounds_are_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            CapacityFrontierRequest.model_validate({
                "capacities": [0, 100],
                "value_unit": "RUB",
            })


if __name__ == "__main__":
    unittest.main()
