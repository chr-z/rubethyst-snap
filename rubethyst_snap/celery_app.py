"""Celery application factory.

A single ``Celery`` instance is shared by the API process (which only
calls ``send_task``) and the worker/beat processes (which actually
execute tasks). Keeping it in one module avoids accidentally minting
two app instances with conflicting task registries.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import schedule

from .api.settings import get_settings


def make_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "rubethyst_snap",
        broker=settings.effective_broker_url,
        backend=settings.effective_result_backend,
        include=["rubethyst_snap.worker.tasks"],
    )
    app.conf.update(
        task_default_queue=settings.celery_default_queue,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        timezone="UTC",
        enable_utc=True,
    )
    app.conf.task_routes = {
        "rubethyst_snap.download_job": {"queue": settings.celery_default_queue},
        "rubethyst_snap.sweep_expired_artifacts": {"queue": settings.celery_default_queue},
        "rubethyst_snap.sweep_download_cemetery": {"queue": settings.celery_default_queue},
    }
    app.conf.beat_schedule = {
        "sweep-expired-artifacts": {
            "task": "rubethyst_snap.sweep_expired_artifacts",
            "schedule": schedule(run_every=settings.cleanup_interval_seconds),
        },
        "sweep-download-cemetery": {
            "task": "rubethyst_snap.sweep_download_cemetery",
            "schedule": schedule(run_every=settings.cemetery_interval_seconds),
        },
    }
    return app


celery_app = make_celery_app()
