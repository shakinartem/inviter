from __future__ import annotations

import unittest

from app.features.orchestration.execution_events import CALIBRATION_CONFOUNDING_EVENTS


class CampaignExecutionEventPolicyTests(unittest.TestCase):
    def test_operator_controls_are_calibration_confounders(self) -> None:
        self.assertTrue(
            {
                "operator_start",
                "operator_pause",
                "operator_stop",
                "operator_config_change",
            }.issubset(CALIBRATION_CONFOUNDING_EVENTS)
        )

    def test_system_failover_is_not_operator_confounder(self) -> None:
        self.assertNotIn("automatic_flood_wait", CALIBRATION_CONFOUNDING_EVENTS)
        self.assertNotIn("adaptive_rebalance", CALIBRATION_CONFOUNDING_EVENTS)


if __name__ == "__main__":
    unittest.main()
