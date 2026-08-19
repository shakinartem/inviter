from __future__ import annotations

import unittest

from app.features.orchestration.sla_calibrator_math import (
    activation_eligible,
    apply_mapping,
    build_monotonic_mapping,
)


class ExecutionSLAGovernanceTests(unittest.TestCase):
    def test_mapping_is_monotonic_even_for_noisy_bins(self) -> None:
        predictions = [0.05] * 20 + [0.15] * 20 + [0.55] * 20 + [0.85] * 20
        outcomes = [1] * 12 + [0] * 8 + [1] * 2 + [0] * 18 + [1] * 8 + [0] * 12 + [1] * 18 + [0] * 2
        mapping = build_monotonic_mapping(predictions, outcomes, prior_strength=8)
        calibrated = [item["calibrated_probability"] for item in mapping]
        self.assertEqual(calibrated, sorted(calibrated))

    def test_empty_bins_remain_shrunk_toward_identity(self) -> None:
        mapping = build_monotonic_mapping([0.15, 0.15], [1, 0], prior_strength=20)
        low = mapping[0]["calibrated_probability"]
        high = mapping[-1]["calibrated_probability"]
        self.assertGreaterEqual(low, 0.0)
        self.assertLessEqual(low, 0.2)
        self.assertGreaterEqual(high, 0.8)
        self.assertLessEqual(high, 1.0)

    def test_apply_mapping_uses_probability_band(self) -> None:
        mapping = build_monotonic_mapping([0.15] * 20 + [0.85] * 20, [0] * 10 + [1] * 10 + [1] * 18 + [0] * 2)
        self.assertLess(apply_mapping(0.15, mapping), apply_mapping(0.85, mapping))

    def test_activation_requires_holdout_and_quality_guard(self) -> None:
        self.assertFalse(
            activation_eligible(
                test_count=19,
                raw_brier=0.20,
                calibrated_brier=0.10,
                raw_ece=0.20,
                calibrated_ece=0.10,
                raw_bias=0.10,
                calibrated_bias=0.05,
            )
        )
        self.assertTrue(
            activation_eligible(
                test_count=20,
                raw_brier=0.20,
                calibrated_brier=0.18,
                raw_ece=0.15,
                calibrated_ece=0.10,
                raw_bias=0.08,
                calibrated_bias=0.04,
            )
        )
        self.assertFalse(
            activation_eligible(
                test_count=20,
                raw_brier=0.20,
                calibrated_brier=0.23,
                raw_ece=0.15,
                calibrated_ece=0.10,
                raw_bias=0.08,
                calibrated_bias=0.04,
            )
        )


if __name__ == "__main__":
    unittest.main()
