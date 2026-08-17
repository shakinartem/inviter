from __future__ import annotations

import unittest
from uuid import uuid4

from app.api.router import api_router
from app.features.experiments.meta import IncrementalYieldMetaService


class IncrementalYieldMetaContractTests(unittest.TestCase):
    def test_static_meta_route_precedes_dynamic_campaign_lift(self) -> None:
        paths = [getattr(route, "path", "") for route in api_router.routes]
        meta_index = paths.index("/experiments/meta-lift")
        lift_index = paths.index("/experiments/campaigns/{campaign_id}/lift")
        self.assertLess(meta_index, lift_index)

    def test_individual_rows_preserve_random_effect_weights(self) -> None:
        effects = [
            {
                "experiment_id": uuid4(),
                "campaign_id": uuid4(),
                "campaign_title": "A",
                "treatment_units": 100,
                "treatment_positives": 10,
                "holdout_units": 100,
                "holdout_positives": 5,
                "effect": 0.05,
                "variance": 0.001,
            },
            {
                "experiment_id": uuid4(),
                "campaign_id": uuid4(),
                "campaign_title": "B",
                "treatment_units": 100,
                "treatment_positives": 8,
                "holdout_units": 100,
                "holdout_positives": 5,
                "effect": 0.03,
                "variance": 0.002,
            },
        ]
        rows = IncrementalYieldMetaService._individual_rows(effects, [1000.0, 500.0], 1500.0)
        self.assertAlmostEqual(sum(row["weight_percent"] for row in rows), 100.0, places=1)
        self.assertGreater(rows[0]["weight_percent"], rows[1]["weight_percent"])

    def test_empty_result_is_explicitly_insufficient(self) -> None:
        result = IncrementalYieldMetaService._empty("business", "converted", 168)
        self.assertEqual(result["status"], "insufficient")
        self.assertIn("no_mature_randomized_experiments", result["warnings"])


if __name__ == "__main__":
    unittest.main()
