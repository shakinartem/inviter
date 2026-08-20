from __future__ import annotations

import unittest

from app.features.experiments.contextual_value import ContextualIncrementalBusinessValueService


class ContextualIncrementalValueContractTests(unittest.TestCase):
    def test_sparse_value_context_shrinks_more_toward_global_prior(self) -> None:
        sparse, sparse_weight = ContextualIncrementalBusinessValueService.shrink_effect(
            contextual_effect=10000.0,
            contextual_variance=25_000_000.0,
            global_effect=2000.0,
            prior_variance=1_000_000.0,
        )
        dense, dense_weight = ContextualIncrementalBusinessValueService.shrink_effect(
            contextual_effect=10000.0,
            contextual_variance=100_000.0,
            global_effect=2000.0,
            prior_variance=1_000_000.0,
        )
        self.assertGreater(dense_weight, sparse_weight)
        self.assertLess(abs(dense - 10000.0), abs(sparse - 10000.0))
        self.assertLess(abs(sparse - 2000.0), abs(dense - 2000.0))

    def test_readiness_bucket_contract_matches_causal_yield(self) -> None:
        bucket = ContextualIncrementalBusinessValueService._readiness_bucket
        self.assertEqual(bucket(0), 0)
        self.assertEqual(bucket(20), 20)
        self.assertEqual(bucket(79.9), 60)
        self.assertEqual(bucket(100), 80)
        self.assertEqual(ContextualIncrementalBusinessValueService._bucket_label(80), "80-100")

    def test_value_variance_keeps_zero_outcomes(self) -> None:
        variance = ContextualIncrementalBusinessValueService._sample_variance([0.0, 0.0, 100.0])
        self.assertGreater(variance, 0.0)


if __name__ == "__main__":
    unittest.main()
