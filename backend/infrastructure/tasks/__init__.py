"""Celery task infrastructure package.

Importing this module wires together the configured Celery app and the
lightweight dispatcher facade that higher layers depend upon.
"""

from .config.celery import celery_app
from .utils.dispatcher import TaskDispatcher

__all__ = ["celery_app", "TaskDispatcher"]
