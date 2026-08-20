from __future__ import annotations

import unittest

from app.features.experiments.value import IncrementalBusinessValueService


class IncrementalBusinessValueContractTests(unittest.TestCase):
    def test_sample_variance_uses_unbiased_denominator(self) -> None:
        variance = IncrementalBusinessValueService._sample_variance([0.0, 10.0, 20.0])
        self.assertAlmostEqual(variance, 100.0)

    def test_zero_only_arm_has_zero_sample_variance(self) -> None:
        self.assertEqual(IncrementalBusinessValueService._sample_variance([0.0, 0.0, 0.0]), 0.0)

    def test_empty_value_history_is_explicitly_insufficient(self) -> None:
        result = IncrementalBusinessValueService._empty(
            "payment_received", "RUB", 168, "sum"
        )
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["value_unit"], "RUB")
        self.assertIn("no_mature_randomized_value_experiments", result["warnings"])


if __name__ == "__main__":
    unittest.main()
