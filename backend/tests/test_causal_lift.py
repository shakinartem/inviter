from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from app.api.router import api_router
from app.features.experiments.analysis import CausalLiftService
from app.features.learning.webhook_schemas import WebhookOutcomePayload


class CausalLiftContractTests(unittest.TestCase):
    def test_wilson_interval_is_bounded(self) -> None:
        low, high = CausalLiftService._wilson_interval(20, 100)
        self.assertGreaterEqual(low, 0)
        self.assertLessEqual(high, 1)
        self.assertLess(low, 0.2)
        self.assertGreater(high, 0.2)

    def test_standardized_difference_is_zero_for_balanced_arms(self) -> None:
        smd = CausalLiftService._standardized_difference([10, 20, 30], [10, 20, 30])
        self.assertEqual(smd, 0)

    def test_assignment_webhook_attribution_is_valid(self) -> None:
        payload = WebhookOutcomePayload.model_validate(
            {
                "event_id": "crm-holdout-1",
                "experiment_assignment_id": str(uuid4()),
                "stage": "business",
                "event_type": "converted",
                "observed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.assertIsNone(payload.action_job_id)
        self.assertIsNotNone(payload.experiment_assignment_id)

    def test_webhook_rejects_ambiguous_attribution(self) -> None:
        with self.assertRaises(ValidationError):
            WebhookOutcomePayload.model_validate(
                {
                    "event_id": "ambiguous",
                    "action_job_id": str(uuid4()),
                    "experiment_assignment_id": str(uuid4()),
                    "stage": "business",
                    "event_type": "converted",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                }
            )

    def test_webhook_rejects_missing_attribution(self) -> None:
        with self.assertRaises(ValidationError):
            WebhookOutcomePayload.model_validate(
                {
                    "event_id": "missing",
                    "stage": "business",
                    "event_type": "converted",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                }
            )

    def test_causal_lift_route_is_registered(self) -> None:
        paths = [getattr(route, "path", "") for route in api_router.routes]
        self.assertIn("/experiments/campaigns/{campaign_id}/lift", paths)


if __name__ == "__main__":
    unittest.main()
