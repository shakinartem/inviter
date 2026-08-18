from __future__ import annotations

import unittest

from app.tasks.celery_app import celery_app


class ExecutionSLAScheduleTests(unittest.TestCase):
    def test_mature_forecasts_are_finalized_hourly(self) -> None:
        schedule = celery_app.conf.beat_schedule
        self.assertIn("orchestration-finalize-execution-sla", schedule)
        item = schedule["orchestration-finalize-execution-sla"]
        self.assertEqual(item["task"], "orchestration.finalize_execution_sla")
        self.assertEqual(float(item["schedule"]), 3600.0)
        self.assertEqual(tuple(item["args"]), (250,))


if __name__ == "__main__":
    unittest.main()
