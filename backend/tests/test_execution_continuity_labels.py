from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.features.orchestration.continuity_labels import label_execution_continuity


class ExecutionContinuityLabelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 8, 19, 3, 0, tzinfo=timezone.utc)

    def test_clean_daily_schedule_meets_continuity(self) -> None:
        successes = [
            self.start + timedelta(hours=1 + hour)
            for hour in range(10)
        ] + [
            self.start + timedelta(days=1, hours=1 + hour)
            for hour in range(10)
        ]
        label = label_execution_continuity(
            forecast_created_at=self.start,
            deadline_at=self.start + timedelta(days=2),
            normal_daily_capacity=10,
            remaining_actions=20,
            successful_finished_at=successes,
        )
        self.assertTrue(label.met_continuity)
        self.assertEqual(label.windows_total, 2)
        self.assertEqual(label.windows_met, 2)
        self.assertEqual(label.remaining_actions_at_deadline, 0)

    def test_late_catch_up_does_not_erase_missed_window(self) -> None:
        successes = [
            self.start + timedelta(hours=1 + hour)
            for hour in range(5)
        ] + [
            self.start + timedelta(days=1, hours=1 + hour)
            for hour in range(15)
        ]
        label = label_execution_continuity(
            forecast_created_at=self.start,
            deadline_at=self.start + timedelta(days=2),
            normal_daily_capacity=10,
            remaining_actions=20,
            successful_finished_at=successes,
        )
        self.assertFalse(label.met_continuity)
        self.assertEqual(label.windows_met, 1)
        self.assertEqual(label.remaining_actions_at_deadline, 0)

    def test_early_overdelivery_can_finish_obligation_early(self) -> None:
        successes = [self.start + timedelta(minutes=minute) for minute in range(1, 16)]
        label = label_execution_continuity(
            forecast_created_at=self.start,
            deadline_at=self.start + timedelta(days=3),
            normal_daily_capacity=10,
            remaining_actions=15,
            successful_finished_at=successes,
        )
        self.assertTrue(label.met_continuity)
        self.assertEqual(label.windows_total, 1)
        self.assertEqual(label.windows_met, 1)

    def test_partial_last_window_is_prorated(self) -> None:
        successes = [self.start + timedelta(hours=1 + hour) for hour in range(5)]
        label = label_execution_continuity(
            forecast_created_at=self.start,
            deadline_at=self.start + timedelta(hours=12),
            normal_daily_capacity=10,
            remaining_actions=5,
            successful_finished_at=successes,
        )
        self.assertTrue(label.met_continuity)
        self.assertEqual(label.windows[0].required_actions, 5)

    def test_continuity_can_hold_even_when_workload_does_not_finish(self) -> None:
        successes = [
            self.start + timedelta(hours=1 + hour)
            for hour in range(10)
        ] + [
            self.start + timedelta(days=1, hours=1 + hour)
            for hour in range(10)
        ]
        label = label_execution_continuity(
            forecast_created_at=self.start,
            deadline_at=self.start + timedelta(days=2),
            normal_daily_capacity=10,
            remaining_actions=30,
            successful_finished_at=successes,
        )
        self.assertTrue(label.met_continuity)
        self.assertEqual(label.windows_met, 2)
        self.assertEqual(label.remaining_actions_at_deadline, 10)


if __name__ == "__main__":
    unittest.main()
