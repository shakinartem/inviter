from __future__ import annotations

import json
import time
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from app.features.learning.webhook_schemas import WebhookOutcomePayload, WebhookSourceCreate
from app.features.learning.webhook_service import (
    OutcomeWebhookService,
    WebhookAuthenticationError,
)


class OutcomeWebhookContractTests(unittest.TestCase):
    def test_signature_is_bound_to_timestamp_and_raw_body(self) -> None:
        secret = "test-secret-for-hmac"
        timestamp = str(int(time.time()))
        body = b'{"event_id":"evt-1"}'
        signature = OutcomeWebhookService.signature_for(secret, timestamp, body)
        self.assertTrue(
            OutcomeWebhookService.verify_signature(
                signing_secret=secret,
                timestamp=timestamp,
                raw_body=body,
                signature_header=signature,
            )
        )
        self.assertFalse(
            OutcomeWebhookService.verify_signature(
                signing_secret=secret,
                timestamp=timestamp,
                raw_body=b'{"event_id":"evt-2"}',
                signature_header=signature,
            )
        )

    def test_old_timestamp_is_rejected(self) -> None:
        old_timestamp = str(int(time.time()) - 1000)
        with self.assertRaises(WebhookAuthenticationError):
            OutcomeWebhookService._parse_and_validate_timestamp(old_timestamp)

    def test_payload_cannot_create_transport_outcome(self) -> None:
        payload = {
            "event_id": "crm-123",
            "action_job_id": str(uuid4()),
            "stage": "transport",
            "event_type": "converted",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        with self.assertRaises(ValidationError):
            WebhookOutcomePayload.model_validate(payload)

    def test_payload_requires_stable_external_event_id(self) -> None:
        payload = {
            "action_job_id": str(uuid4()),
            "stage": "business",
            "event_type": "converted",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        with self.assertRaises(ValidationError):
            WebhookOutcomePayload.model_validate(payload)

    def test_event_types_are_normalized_and_deduplicated(self) -> None:
        source = WebhookSourceCreate(
            name="CRM",
            allowed_event_types=["Payment Received", "payment_received", " Converted "],
        )
        self.assertEqual(source.allowed_event_types, ["payment_received", "converted"])

    def test_slug_normalization_is_stable(self) -> None:
        self.assertEqual(OutcomeWebhookService._normalize_slug(" CRM / Integrator "), "crm-integrator")

    def test_raw_json_payload_round_trips(self) -> None:
        raw = json.dumps(
            {
                "event_id": "crm-1",
                "action_job_id": str(uuid4()),
                "stage": "business",
                "event_type": "Payment Received",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "value": 120000,
            }
        ).encode()
        payload = WebhookOutcomePayload.model_validate_json(raw)
        self.assertEqual(payload.event_type, "payment_received")
        self.assertEqual(payload.value, 120000)


if __name__ == "__main__":
    unittest.main()
