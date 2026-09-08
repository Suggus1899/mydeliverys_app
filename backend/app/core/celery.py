from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "mydeliverys",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.exchange_rate",
        "app.tasks.reservations",
        "app.tasks.notifications",
        "app.tasks.outbox",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Caracas",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    result_expires=3600,
    beat_schedule={
        "fetch-exchange-rate-every-30-minutes": {
            "task": "app.tasks.exchange_rate.fetch_exchange_rate",
            "schedule": 1800.0,  # 30 minutes
        },
        "expire-reservations-every-minute": {
            "task": "app.tasks.reservations.expire_reservations",
            "schedule": 60.0,  # 1 minute
        },
        "publish-order-events-every-10-seconds": {
            "task": "app.tasks.outbox.publish_order_events",
            "schedule": 10.0,
        },
        "cleanup-idempotency-keys-daily": {
            "task": "app.tasks.maintenance.cleanup_idempotency_keys",
            "schedule": crontab(hour=3, minute=0),  # 3 AM daily
        },
        "cleanup-expired-sessions-daily": {
            "task": "app.tasks.maintenance.cleanup_expired_sessions",
            "schedule": crontab(hour=4, minute=0),  # 4 AM daily
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])


@celery_app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
