"""Task modules grouped by domain.

Import side effects register Celery tasks once this package is imported.
"""

from . import email  # noqa: F401 to register tasks

__all__ = ["email"]
