"""Small dispatching helpers to decouple Celery from callers."""

from __future__ import annotations

from typing import Any, Dict

from ..config.celery import celery_app


class TaskDispatcher:
    """Internal facade used by application layer to schedule tasks."""

    def send_user_welcome_email(self, user_id: int, email: str) -> None:
        """Fire-and-forget helper for the common welcome email use case."""
        celery_app.send_task(
            "infrastructure.tasks.tasks.email.send_welcome_email",
            kwargs={"user_id": user_id, "email": email},
        )

    def enqueue(
        self, task_name: str, *, args: tuple | None = None, kwargs: Dict[str, Any] | None = None
    ) -> None:
        """Generic escape hatch for scheduling arbitrary tasks by name."""
        celery_app.send_task(task_name, args=args or (), kwargs=kwargs or {})
