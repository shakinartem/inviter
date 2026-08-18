from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.features.orchestration.sla_calibration import (
    calibration_metrics,
    current_workload_completion_probability,
)


class ExecutionSLACalibrationTests(unittest.TestCase):
    def test_current_probability_uses_current_reserve_not_recommendation(self) -> None:
        snapshot = SimpleNamespace(
            current_reserve_percentage=20.0,
            scenarios_snapshot=[
                {"reserve_percentage": 0.0, "modelled_workload_completion_probability": 0.91},
                {"reserve_percentage": 20.0, "modelled_workload_completion_probability": 0.72},
                {"reserve_percentage": 40.0, "modelled_workload_completion_probability": 0.40},
            ],
        )
        self.assertEqual(current_workload_completion_probability(snapshot), 0.72)

    def test_brier_and_bias_for_symmetric_predictions(self) -> None:
        metrics = calibration_metrics([0.8, 0.2], [1, 0])
        self.assertEqual(metrics["mean_prediction"], 0.5)
        self.assertEqual(metrics["observed_completion_rate"], 0.5)
        self.assertEqual(metrics["calibration_bias"], 0.0)
        self.assertAlmostEqual(metrics["brier_score"], 0.04, places=4)
        self.assertAlmostEqual(metrics["expected_calibration_error"], 0.2, places=4)

    def test_perfect_predictions_have_zero_brier(self) -> None:
        metrics = calibration_metrics([1.0, 0.0, 1.0, 0.0], [1, 0, 1, 0])
        self.assertEqual(metrics["brier_score"], 0.0)
        self.assertEqual(metrics["expected_calibration_error"], 0.0)

    def test_empty_calibration_is_explicit(self) -> None:
        metrics = calibration_metrics([], [])
        self.assertIsNone(metrics["brier_score"])
        self.assertEqual(metrics["buckets"], [])


if __name__ == "__main__":
    unittest.main()
