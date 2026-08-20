from __future__ import annotations

import unittest

from app.api.router import api_router
from app.features.experiments.contextual import ContextualIncrementalYieldService


class ContextualIncrementalYieldContractTests(unittest.TestCase):
    def test_static_contextual_route_precedes_dynamic_campaign_lift(self) -> None:
        paths = [getattr(route, "path", "") for route in api_router.routes]
        contextual_index = paths.index("/experiments/contextual-lift")
        lift_index = paths.index("/experiments/campaigns/{campaign_id}/lift")
        self.assertLess(contextual_index, lift_index)

    def test_readiness_bucket_boundaries(self) -> None:
        bucket = ContextualIncrementalYieldService._readiness_bucket
        self.assertEqual(bucket(0), 0)
        self.assertEqual(bucket(19.99), 0)
        self.assertEqual(bucket(20), 20)
        self.assertEqual(bucket(79.9), 60)
        self.assertEqual(bucket(80), 80)
        self.assertEqual(bucket(100), 80)
        self.assertEqual(bucket(120), 80)

    def test_sparse_context_shrinks_more_toward_global_prior(self) -> None:
        sparse, sparse_weight = ContextualIncrementalYieldService.shrink_effect(
            contextual_effect=0.10,
            contextual_variance=0.01,
            global_effect=0.02,
            prior_variance=0.001,
        )
        dense, dense_weight = ContextualIncrementalYieldService.shrink_effect(
            contextual_effect=0.10,
            contextual_variance=0.0001,
            global_effect=0.02,
            prior_variance=0.001,
        )
        self.assertGreater(dense_weight, sparse_weight)
        self.assertLess(abs(dense - 0.10), abs(sparse - 0.10))
        self.assertLess(abs(sparse - 0.02), abs(dense - 0.02))

    def test_single_within_stratum_contrast_is_preserved(self) -> None:
        effect, variance = ContextualIncrementalYieldService._pool_within_stratum(
            [{"effect": 0.04, "variance": 0.0025}]
        )
        self.assertEqual(effect, 0.04)
        self.assertEqual(variance, 0.0025)

    def test_bucket_label_keeps_100_inside_top_bucket(self) -> None:
        self.assertEqual(ContextualIncrementalYieldService._bucket_label(80), "80-100")


if __name__ == "__main__":
    unittest.main()
