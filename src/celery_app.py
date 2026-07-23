from datetime import timedelta
from celery import Celery
from src.config.settings import settings

celery_app = Celery("online_cinema")

celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    "clear-tokens-for-test": {
        "task": "cleanup_expired_tokens_task",
        "schedule": timedelta(minutes=1),
    },
}

celery_app.autodiscover_tasks(['src.tasks'])
