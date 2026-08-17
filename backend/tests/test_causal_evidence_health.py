from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.features.experiments.evidence_health import CausalEvidenceHealthService
from app.features.experiments.evidence_health_schemas import EvidenceHealthRequest


class CausalEvidenceHealthContractTests(unittest.TestCase):
    def test_business_value_requires_and_normalizes_unit(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceHealthRequest.model_validate({
                "objective": "incremental_business_value",
                "value_unit": None,
            })

        payload = EvidenceHealthRequest.model_validate({
            "objective": "incremental_business_value",
            "event_type": "payment_received",
            "value_unit": "rub",
        })
        self.assertEqual(payload.value_unit, "RUB")
        self.assertEqual(payload.stage, "business")
        self.assertEqual(payload.value_aggregation, "sum")

    def test_outcome_objective_drops_value_fields(self) -> None:
        payload = EvidenceHealthRequest.model_validate({
            "objective": "incremental_outcomes",
            "event_type": "converted",
            "value_unit": "RUB",
            "value_aggregation": "max",
        })
        self.assertIsNone(payload.value_unit)
        self.assertIsNone(payload.value_aggregation)

    def test_equal_precision_effects_pool_to_midpoint(self) -> None:
        pooled = CausalEvidenceHealthService._pool([
            {"effect": 2.0, "se": 1.0},
            {"effect": 4.0, "se": 1.0},
        ])
        self.assertEqual(pooled["experiments"], 2)
        self.assertAlmostEqual(pooled["estimate"], 3.0)
        self.assertIsNotNone(pooled["confidence_low"])
        self.assertIsNotNone(pooled["confidence_high"])

    def test_empty_window_is_explicit(self) -> None:
        pooled = CausalEvidenceHealthService._pool([])
        self.assertEqual(pooled["experiments"], 0)
        self.assertIsNone(pooled["estimate"])
        self.assertIsNone(pooled["variance"])


if __name__ == "__main__":
    unittest.main()
