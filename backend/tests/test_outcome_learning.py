from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from app.features.learning.schemas import ObservedOutcomeCreate
from app.features.learning.service import OutcomeLearningService


class OutcomeLearningTests(unittest.TestCase):
    def test_wilson_interval_for_empty_sample_is_zero(self) -> None:
        low, high = OutcomeLearningService._wilson_interval(0, 0)
        self.assertEqual(low, 0.0)
        self.assertEqual(high, 0.0)

    def test_wilson_interval_contains_observed_rate(self) -> None:
        low, high = OutcomeLearningService._wilson_interval(5, 10)
        self.assertGreaterEqual(low, 0.0)
        self.assertLessEqual(high, 1.0)
        self.assertLess(low, 0.5)
        self.assertGreater(high, 0.5)

    def test_idempotency_key_takes_precedence_over_external_event(self) -> None:
        job_id = uuid4()
        key = OutcomeLearningService._external_dedupe_key(
            job_id=job_id,
            stage="business",
            event_type="converted",
            source="crm",
            observed_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
            external_event_id="external-123",
            idempotency_key="conversion-abc",
        )
        self.assertEqual(key, "idempotency:crm:conversion-abc")

    def test_external_event_id_is_stable_dedupe_key(self) -> None:
        job_id = uuid4()
        first = OutcomeLearningService._external_dedupe_key(
            job_id=job_id,
            stage="engagement",
            event_type="replied",
            source="telegram_observer",
            observed_at=datetime(2026, 8, 17, 10, tzinfo=timezone.utc),
            external_event_id="msg-42",
            idempotency_key=None,
        )
        second = OutcomeLearningService._external_dedupe_key(
            job_id=uuid4(),
            stage="business",
            event_type="converted",
            source="telegram_observer",
            observed_at=datetime(2026, 8, 18, 10, tzinfo=timezone.utc),
            external_event_id="msg-42",
            idempotency_key=None,
        )
        self.assertEqual(first, second)
        self.assertEqual(first, "external:telegram_observer:msg-42")

    def test_derived_dedupe_key_changes_with_observation(self) -> None:
        job_id = uuid4()
        first = OutcomeLearningService._external_dedupe_key(
            job_id=job_id,
            stage="engagement",
            event_type="joined",
            source="manual",
            observed_at=datetime(2026, 8, 17, 10, tzinfo=timezone.utc),
            external_event_id=None,
            idempotency_key=None,
        )
        second = OutcomeLearningService._external_dedupe_key(
            job_id=job_id,
            stage="engagement",
            event_type="joined",
            source="manual",
            observed_at=datetime(2026, 8, 17, 11, tzinfo=timezone.utc),
            external_event_id=None,
            idempotency_key=None,
        )
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("derived:"))

    def test_manual_api_does_not_accept_transport_stage(self) -> None:
        with self.assertRaises(ValidationError):
            ObservedOutcomeCreate(
                action_job_id=uuid4(),
                stage="transport",  # type: ignore[arg-type]
                event_type="invited",
            )

    def test_manual_api_accepts_business_conversion(self) -> None:
        payload = ObservedOutcomeCreate(
            action_job_id=uuid4(),
            stage="business",
            event_type="converted",
            source="crm",
            confidence=0.9,
            value=125000.0,
        )
        self.assertEqual(payload.stage, "business")
        self.assertEqual(payload.event_type, "converted")
        self.assertEqual(payload.source, "crm")
        self.assertEqual(payload.value, 125000.0)


if __name__ == "__main__":
    unittest.main()
