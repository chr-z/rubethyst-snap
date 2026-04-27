"""Console entrypoints for the Celery worker and beat scheduler."""

from __future__ import annotations

import sys

from ..api.settings import get_settings
from ..celery_app import celery_app


def run_worker() -> None:
    settings = get_settings()
    queues = ",".join({settings.celery_default_queue, settings.celery_pro_queue})
    argv = [
        "worker",
        "--loglevel=INFO",
        f"--queues={queues}",
        "--concurrency=2",
        *sys.argv[1:],
    ]
    celery_app.worker_main(argv)


def run_beat() -> None:
    argv = ["beat", "--loglevel=INFO", *sys.argv[1:]]
    celery_app.start(argv)


if __name__ == "__main__":
    run_worker()
