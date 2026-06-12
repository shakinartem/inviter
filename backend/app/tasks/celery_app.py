from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "inviter",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.features.inviter.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    timezone=settings.timezone,
    broker_connection_retry_on_startup=True,
    beat_schedule={},
)