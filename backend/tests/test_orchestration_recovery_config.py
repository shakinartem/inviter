import unittest

from app.tasks.celery_app import celery_app


class OrchestrationRecoveryConfigTests(unittest.TestCase):
    def test_recovery_task_runs_before_stale_dispatches_can_stick_forever(self):
        schedule = celery_app.conf.beat_schedule
        recovery = schedule.get("orchestration-recover-stale-jobs")
        self.assertIsNotNone(recovery)
        self.assertEqual(recovery["task"], "orchestration.recover_stale_jobs")
        self.assertLessEqual(float(recovery["schedule"]), 60.0)

    def test_worker_prefetch_is_one_for_rate_limited_actions(self):
        self.assertEqual(celery_app.conf.worker_prefetch_multiplier, 1)

    def test_db_state_is_primary_and_celery_uses_early_ack(self):
        self.assertFalse(celery_app.conf.task_acks_late)


if __name__ == "__main__":
    unittest.main()
