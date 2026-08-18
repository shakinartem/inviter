from __future__ import annotations

import unittest
from collections import defaultdict
from datetime import datetime, timezone

from app.features.orchestration.adaptive import MOVABLE_STATUSES, POLICY_VERSION, AdaptiveExecutionService
from app.features.orchestration.adaptive_schemas import AdaptivePolicyResponse


class AdaptiveExecutionPolicyTests(unittest.TestCase):
    def test_only_planned_jobs_are_policy_movable(self) -> None:
        self.assertEqual(MOVABLE_STATUSES, {"planned"})
        policy = AdaptivePolicyResponse()
        self.assertEqual(policy.policy_version, POLICY_VERSION)
        self.assertEqual(policy.attempts_must_equal, 0)
        self.assertIn("pinned", policy.retry_rule)

    def test_capacity_slot_never_overbooks_full_day(self) -> None:
        desired = datetime(2026, 8, 19, 10, 30, tzinfo=timezone.utc)
        counts = defaultdict(int)
        counts[desired.date()] = 3
        slot = AdaptiveExecutionService._next_capacity_slot(
            desired_at=desired,
            daily_limit=3,
            daily_counts=counts,
        )
        self.assertGreater(slot, desired)
        self.assertNotEqual(slot.date(), desired.date())
        self.assertEqual(slot.hour, desired.hour)
        self.assertEqual(slot.minute, desired.minute)

    def test_capacity_slot_keeps_original_time_when_capacity_exists(self) -> None:
        desired = datetime(2026, 8, 19, 10, 30, tzinfo=timezone.utc)
        counts = defaultdict(int)
        counts[desired.date()] = 2
        slot = AdaptiveExecutionService._next_capacity_slot(
            desired_at=desired,
            daily_limit=3,
            daily_counts=counts,
        )
        self.assertEqual(slot, desired)


if __name__ == "__main__":
    unittest.main()
