"""Common base task for Celery jobs"""

from __future__ import annotations

from celery import Task
from core.logging_config import get_logger

logger = get_logger(__name__)


class BaseTask(Task):
    """Provides unified failure logging and hooks for future extensions."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # type: ignore[override]
        """Emit a structured error message before the default Celery handling."""
        logger.error(
            "celery_task_failure",
            task_id=task_id,
            task_name=self.name,
            args=args,
            kwargs=kwargs,
            exc=str(exc),
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):  # type: ignore[override]
        """Log a success event so operators can trace normal execution."""
        logger.info(
            "celery_task_success",
            task_id=task_id,
            task_name=self.name,
        )
        super().on_success(retval, task_id, args, kwargs)
