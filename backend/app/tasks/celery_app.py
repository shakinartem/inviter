from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "inviter",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.features.inviter.tasks",
        "app.features.orchestration.tasks",
        "app.features.learning.tasks",
    ],
)

celery_app.conf.update(
    task_track_started=True,
    timezone=settings.timezone,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "orchestration-dispatch-due-jobs": {
            "task": "orchestration.dispatch_due",
            "schedule": 15.0,
            "args": (100,),
        },
        "orchestration-finalize-execution-sla": {
            "task": "orchestration.finalize_execution_sla",
            "schedule": 3600.0,
            "args": (250,),
        },
        "learning-observe-engagement": {
            "task": "learning.observe_engagement",
            "schedule": 300.0,
            "args": (50, 30, 5000),
        },
    },
)
