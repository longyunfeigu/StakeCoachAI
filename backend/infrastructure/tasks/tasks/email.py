"""Email related Celery tasks"""

from __future__ import annotations

from celery import shared_task

from ..utils.base_task import BaseTask
from core.logging_config import get_logger

logger = get_logger(__name__)


@shared_task(
    bind=True,
    base=BaseTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def send_welcome_email(self, user_id: int, email: str) -> None:
    """Send a welcome email to the specified user.

    Replace the body with real email integration (SMTP/ESP).
    """
    logger.info("send_welcome_email", user_id=user_id, email=email)
