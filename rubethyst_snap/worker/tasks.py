from __future__ import annotations

import logging
from datetime import datetime, timezone

from celery import Task

from ..api.deps import get_redis, get_storage
from ..api.schemas import JobResult
from ..api.settings import get_settings
from ..api.sse import publish_progress_sync
from ..api.tokens import signed_download_url
from ..celery_app import celery_app
from ..core import download
from ..core.exceptions import RubethystError
from ..core.progress import ProgressEvent, ProgressStatus
from ..jobs.redis_repo import RedisJobRepository
from ..quotas.concurrency import release_slot
from ..quotas.plans import PlanName, plan_for
from .cleanup import sweep_cemetery, sweep_expired

log = logging.getLogger(__name__)


def _make_repo(plan_name: str) -> RedisJobRepository:
    settings = get_settings()
    plan = plan_for(PlanName(plan_name), settings)
    return RedisJobRepository(get_redis(), ttl_seconds=plan.retention_hours * 3600)


@celery_app.task(
    bind=True,
    name="rubethyst_snap.download_job",
    autoretry_for=(ConnectionError, OSError),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def download_job(
    self: Task,
    job_id: str,
    url: str,
    preset: str,
    plan_name: str,
    identity: str,
    format_id: str | None = None,
) -> dict:
    """Run one download to completion. Idempotent across retries."""

    settings = get_settings()
    repo = _make_repo(plan_name)
    plan = plan_for(PlanName(plan_name), settings)
    storage = get_storage()
    redis = get_redis()
    workdir = storage.workdir(job_id)

    if self.request.retries:
        publish_progress_sync(
            redis,
            job_id,
            ProgressEvent(
                status=ProgressStatus.RETRYING,
                message=f"retry {self.request.retries}/{self.max_retries}",
            ),
        )

    def on_progress(event: ProgressEvent) -> None:
        repo.update_progress(job_id, event)
        publish_progress_sync(redis, job_id, event)

    try:
        result = download(
            url,
            output_dir=workdir,
            preset=preset,
            progress=on_progress,
            max_duration_seconds=plan.max_duration_seconds,
            max_filesize_bytes=plan.max_filesize_mb * 1024 * 1024,
            format_id=format_id,
        )
    except RubethystError as exc:
        repo.fail(job_id, str(exc))
        publish_progress_sync(
            redis,
            job_id,
            ProgressEvent(status=ProgressStatus.ERROR, message=str(exc)),
        )
        release_slot(redis, identity)
        raise
    except Exception as exc:
        log.exception("unexpected error in download_job %s", job_id)
        repo.fail(job_id, f"unexpected: {exc}")
        publish_progress_sync(
            redis,
            job_id,
            ProgressEvent(status=ProgressStatus.ERROR, message=str(exc)),
        )
        release_slot(redis, identity)
        raise

    artifact_path = str(result.output_path)
    repo.attach_metadata(
        job_id,
        title=result.metadata.title,
        duration=result.metadata.duration_seconds,
        extractor=result.metadata.extractor,
        artifact_path=artifact_path,
    )

    url_str, expires_at = signed_download_url(
        settings,
        job_id=job_id,
        filename=result.output_path.name,
        identity=identity,
    )

    job_result = JobResult(
        download_url=url_str,
        expires_at=expires_at,
        filename=result.output_path.name,
        size_bytes=result.bytes_written,
        container=result.container,
    )
    repo.finish(job_id, job_result)
    publish_progress_sync(
        redis,
        job_id,
        ProgressEvent(
            status=ProgressStatus.FINISHED,
            percent=100.0,
            downloaded_bytes=result.bytes_written,
            total_bytes=result.bytes_written,
        ),
    )
    release_slot(redis, identity)
    return {
        "job_id": job_id,
        "filename": result.output_path.name,
        "size_bytes": result.bytes_written,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="rubethyst_snap.sweep_expired_artifacts")
def sweep_expired_artifacts() -> dict:
    settings = get_settings()
    storage = get_storage()
    redis = get_redis()
    return sweep_expired(redis=redis, storage=storage, settings=settings)


@celery_app.task(name="rubethyst_snap.sweep_download_cemetery")
def sweep_download_cemetery() -> dict:
    settings = get_settings()
    storage = get_storage()
    redis = get_redis()
    return sweep_cemetery(redis=redis, storage=storage, settings=settings)
