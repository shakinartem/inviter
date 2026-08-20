from __future__ import annotations

import unittest

from app.features.orchestration.sla_live_monitoring import live_status


class ExecutionSLALiveMonitoringTests(unittest.TestCase):
    def test_small_post_activation_sample_never_recommends_retirement(self) -> None:
        status, retire = live_status(
            samples=19,
            raw_brier=0.20,
            calibrated_brier=0.50,
            raw_ece=0.10,
            calibrated_ece=0.40,
            raw_bias=0.05,
            calibrated_bias=0.30,
            holdout_calibrated_brier=0.18,
            holdout_calibrated_ece=0.08,
        )
        self.assertEqual(status, "insufficient")
        self.assertFalse(retire)

    def test_developing_sample_is_watch_only(self) -> None:
        status, retire = live_status(
            samples=30,
            raw_brier=0.20,
            calibrated_brier=0.35,
            raw_ece=0.10,
            calibrated_ece=0.30,
            raw_bias=0.04,
            calibrated_bias=0.20,
            holdout_calibrated_brier=0.18,
            holdout_calibrated_ece=0.08,
        )
        self.assertEqual(status, "watch")
        self.assertFalse(retire)

    def test_material_live_degradation_recommends_revalidation(self) -> None:
        status, retire = live_status(
            samples=60,
            raw_brier=0.19,
            calibrated_brier=0.24,
            raw_ece=0.08,
            calibrated_ece=0.16,
            raw_bias=0.03,
            calibrated_bias=0.10,
            holdout_calibrated_brier=0.17,
            holdout_calibrated_ece=0.07,
        )
        self.assertEqual(status, "revalidation_required")
        self.assertTrue(retire)

    def test_calibrator_can_be_healthy_when_live_quality_matches_raw(self) -> None:
        status, retire = live_status(
            samples=80,
            raw_brier=0.20,
            calibrated_brier=0.19,
            raw_ece=0.10,
            calibrated_ece=0.09,
            raw_bias=0.04,
            calibrated_bias=0.03,
            holdout_calibrated_brier=0.18,
            holdout_calibrated_ece=0.08,
        )
        self.assertEqual(status, "healthy")
        self.assertFalse(retire)


if __name__ == "__main__":
    unittest.main()
