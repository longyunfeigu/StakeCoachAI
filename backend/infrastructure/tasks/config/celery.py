"""Celery application configuration"""

from __future__ import annotations

import os
from core.logging_config import get_logger
from celery import Celery
from kombu import Queue

from core.config import settings
from .beat import CELERY_BEAT_SCHEDULE


# Task modules are discovered via this tuple so new packages only need to be
# listed here rather than altering the runtime imports scattered elsewhere.
CELERY_IMPORTS = ("infrastructure.tasks.tasks",)


celery_app = Celery("fastapi_forge")

celery_app.conf.update(
    # Connection endpoints – fall back to env variables when settings omit them.
    broker_url=settings.redis.url or os.getenv("CELERY_BROKER_URL"),
    result_backend=settings.redis.url or os.getenv("CELERY_RESULT_BACKEND"),
    # JSON keeps payloads interoperable and avoids arbitrary code execution.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Ensure acknowledgements happen after work is done so retries are possible.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    # Auto-expire stale results to keep the backend tidy.
    result_expires=3600,
    # Avoid the worker grabbing more than it can process, aiding fairness.
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_default_retry_delay=5,
    # Predeclare queues so routing/priority rules are explicit and easy to
    # extend when new workloads arrive.
    task_queues=(
        Queue("high"),
        Queue("default"),
        Queue("low"),
    ),
    # Default routing – additional entries can be added per domain module.
    task_routes={
        "infrastructure.tasks.tasks.email.*": {"queue": "default"},
    },
    beat_schedule=CELERY_BEAT_SCHEDULE,
)

celery_app.conf.imports = CELERY_IMPORTS

environment = getattr(settings, "ENVIRONMENT", "production") or "production"
if environment.lower() in {"development", "dev", "test", "testing"}:
    celery_app.conf.task_always_eager = True

celery_app.autodiscover_tasks(packages=CELERY_IMPORTS)


logger = get_logger(__name__)


@celery_app.on_after_configure.connect
def _log_configuration(sender, **kwargs):
    logger.info(
        "celery_configured",
        broker=sender.conf.broker_url,
        result_backend=sender.conf.result_backend,
    )
