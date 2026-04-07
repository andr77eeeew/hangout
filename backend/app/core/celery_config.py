from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "hangout_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=30,
)

celery_app.autodiscover_tasks(["app.tasks", "app.services", "app.tasks.rawg"])
