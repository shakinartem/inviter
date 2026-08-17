from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.features.learning.observer import (
    CURSOR_OVERLAP_SECONDS,
    AutomaticOutcomeObserver,
)


class AutomaticOutcomeObserverTests(unittest.TestCase):
    def test_first_scan_never_precedes_transport_or_global_lookback(self) -> None:
        now = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
        old_transport = now - timedelta(days=60)
        since = AutomaticOutcomeObserver._scan_since(
            cursor_last_observed_at=None,
            earliest_transport_at=old_transport,
            now=now,
            lookback_days=30,
        )
        self.assertEqual(since, now - timedelta(days=30))

    def test_first_scan_starts_at_transport_when_inside_lookback(self) -> None:
        now = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
        transport = now - timedelta(days=2)
        since = AutomaticOutcomeObserver._scan_since(
            cursor_last_observed_at=None,
            earliest_transport_at=transport,
            now=now,
            lookback_days=30,
        )
        self.assertEqual(since, transport)

    def test_cursor_uses_small_overlap_to_avoid_boundary_loss(self) -> None:
        now = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
        transport = now - timedelta(days=2)
        cursor = now - timedelta(minutes=5)
        since = AutomaticOutcomeObserver._scan_since(
            cursor_last_observed_at=cursor,
            earliest_transport_at=transport,
            now=now,
            lookback_days=30,
        )
        self.assertEqual(since, cursor - timedelta(seconds=CURSOR_OVERLAP_SECONDS))

    def test_cursor_overlap_cannot_cross_original_transport_boundary(self) -> None:
        now = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
        transport = now - timedelta(minutes=2)
        cursor = transport + timedelta(seconds=30)
        since = AutomaticOutcomeObserver._scan_since(
            cursor_last_observed_at=cursor,
            earliest_transport_at=transport,
            now=now,
            lookback_days=30,
        )
        self.assertEqual(since, transport)

    def test_datetime_normalization_accepts_iso_z(self) -> None:
        parsed = AutomaticOutcomeObserver._normalize_datetime("2026-08-17T12:30:00Z")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.hour, 12)

    def test_datetime_normalization_rejects_garbage(self) -> None:
        self.assertIsNone(AutomaticOutcomeObserver._normalize_datetime("not-a-date"))


if __name__ == "__main__":
    unittest.main()
