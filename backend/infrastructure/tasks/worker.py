"""Convenience entry point for running Celery worker.

Most deployments will invoke the standard Celery CLI, but keeping a small
script makes local testing or Procfile-style runners straightforward.
"""

from __future__ import annotations

from celery.bin import worker

from .config.celery import celery_app


def main() -> None:
    worker_app = worker.worker(app=celery_app)
    worker_app.run(
        hostname="worker@%h",
        detach=False,
    )


if __name__ == "__main__":
    main()
