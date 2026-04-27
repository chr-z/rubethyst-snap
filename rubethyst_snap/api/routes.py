from __future__ import annotations

import mimetypes
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from ..core.exceptions import MetadataError, UnsupportedURLError
from ..core.formats import PRESETS
from ..core.metadata import extract_metadata
from ..jobs.redis_repo import RedisJobRepository
from ..quotas.concurrency import acquire_slot
from ..quotas.plans import Plan
from .deps import (
    enforce_rate_limit,
    get_redis,
    get_repository,
    get_storage,  # noqa: F401  (re-exported for tests / future use)
    require_plan_and_identity,
)
from .health import build_health_response
from .schemas import (
    FormatOut,
    HealthResponse,
    Job,
    JobCreate,
    JobProgress,
    PreviewRequest,
    PreviewResponse,
)
from .settings import Settings, get_settings
from .sse import progress_event_stream
from .tokens import signed_download_url, verify_download_token

router = APIRouter()


@router.get("/healthz", tags=["meta"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/health", response_model=HealthResponse, tags=["meta"])
def health(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    return build_health_response(settings, get_redis())


@router.get("/api/v1/presets", tags=["meta"])
def list_presets() -> dict[str, dict[str, str]]:
    return {name: {"description": p.description} for name, p in PRESETS.items()}


@router.get("/api/v1/plan", tags=["meta"])
def describe_plan(
    deps: tuple[Plan, str] = Depends(require_plan_and_identity),
) -> dict[str, object]:
    plan, _ = deps
    return {
        "name": plan.name.value,
        "max_duration_seconds": plan.max_duration_seconds,
        "max_filesize_mb": plan.max_filesize_mb,
        "max_height": plan.max_height,
        "concurrency": plan.concurrency,
        "rate_per_hour": plan.rate_per_hour,
        "retention_hours": plan.retention_hours,
        "allowed_presets": sorted(plan.allowed_presets),
    }


@router.post("/api/v1/preview", response_model=PreviewResponse, tags=["jobs"])
async def preview(
    payload: PreviewRequest,
    _deps: tuple[Plan, str] = Depends(enforce_rate_limit),
) -> PreviewResponse:
    """Cheap metadata-only fetch to power the dashboard before enqueueing."""

    try:
        meta = await run_in_threadpool(extract_metadata, str(payload.url))
    except UnsupportedURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MetadataError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return PreviewResponse(
        title=meta.title,
        extractor=meta.extractor,
        duration_seconds=meta.duration_seconds,
        thumbnail=meta.thumbnail,
        uploader=meta.uploader,
        is_live=meta.is_live,
        was_live=meta.was_live,
        formats=[FormatOut(**asdict(f)) for f in meta.formats],
    )


@router.post(
    "/api/v1/jobs",
    response_model=Job,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["jobs"],
)
async def create_job(
    payload: JobCreate,
    settings: Settings = Depends(get_settings),
    deps: tuple[Plan, str] = Depends(enforce_rate_limit),
    repo: RedisJobRepository = Depends(get_repository),
) -> Job:
    plan, identity = deps

    if payload.preset not in PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown preset {payload.preset!r}")
    if payload.preset not in plan.allowed_presets:
        raise HTTPException(
            status_code=403,
            detail=f"Preset {payload.preset!r} not allowed on plan {plan.name.value!r}",
        )

    try:
        meta = await run_in_threadpool(extract_metadata, str(payload.url))
    except UnsupportedURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MetadataError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if meta.duration_seconds and meta.duration_seconds > plan.max_duration_seconds:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Video duration {meta.duration_seconds}s exceeds plan limit "
                f"{plan.max_duration_seconds}s"
            ),
        )

    slot = acquire_slot(
        get_redis(),
        identity,
        limit=plan.concurrency,
        ttl_seconds=plan.max_duration_seconds + 600,
    )
    if not slot.acquired:
        from ..quotas.concurrency import release_slot

        release_slot(get_redis(), identity)
        raise HTTPException(
            status_code=409,
            detail=(
                f"Concurrency limit reached: {plan.concurrency} simultaneous "
                f"job(s) on plan {plan.name.value!r}"
            ),
        )

    now = datetime.now(timezone.utc)
    job_id = uuid.uuid4().hex
    job = Job(
        id=job_id,
        url=str(payload.url),
        preset=payload.preset,
        plan=plan.name,
        identity=identity,
        created_at=now,
        updated_at=now,
        retention_until=now + timedelta(hours=plan.retention_hours),
        progress=JobProgress(status="queued"),  # type: ignore[arg-type]
        title=meta.title,
        duration_seconds=meta.duration_seconds,
        extractor=meta.extractor,
    )
    repo.create(job)

    # Lazy import to avoid loading Celery when running the desktop app.
    from ..celery_app import celery_app

    format_id = (payload.format_id or "").strip() or None
    if format_id:
        requested_height: int | None = None
        for fmt in meta.formats:
            if fmt.format_id == format_id:
                requested_height = fmt.height
                break
        if requested_height and requested_height > plan.max_height:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Format {format_id!r} exceeds plan {plan.name.value!r} "
                    f"max height ({plan.max_height}p)"
                ),
            )

    celery_app.send_task(
        "rubethyst_snap.download_job",
        args=[
            job_id,
            str(payload.url),
            payload.preset,
            plan.name.value,
            identity,
            format_id,
        ],
        queue=plan.queue,
    )
    return job


@router.get("/api/v1/jobs/{job_id}", response_model=Job, tags=["jobs"])
def get_job(
    job_id: str,
    repo: RedisJobRepository = Depends(get_repository),
    _deps: tuple[Plan, str] = Depends(require_plan_and_identity),
) -> Job:
    job = repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found or expired")
    return job


@router.get("/api/v1/jobs/{job_id}/stream", tags=["jobs"])
async def stream_job_progress(
    job_id: str,
    repo: RedisJobRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
    _deps: tuple[Plan, str] = Depends(require_plan_and_identity),
) -> EventSourceResponse:
    job = repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found or expired")

    initial = None
    if job.progress is not None:
        from ..core.progress import ProgressEvent

        initial = ProgressEvent(
            status=job.progress.status,
            percent=job.progress.percent,
            downloaded_bytes=job.progress.downloaded_bytes,
            total_bytes=job.progress.total_bytes,
            speed_bps=job.progress.speed_bps,
            eta_seconds=job.progress.eta_seconds,
            message=job.progress.message,
        )

    generator = progress_event_stream(
        settings.redis_url,
        job_id,
        initial_event=initial,
    )
    return EventSourceResponse(generator)


@router.post(
    "/api/v1/jobs/{job_id}/download-url",
    tags=["jobs"],
)
def mint_download_url(
    job_id: str,
    settings: Settings = Depends(get_settings),
    repo: RedisJobRepository = Depends(get_repository),
    deps: tuple[Plan, str] = Depends(require_plan_and_identity),
) -> dict[str, object]:
    """Return a fresh signed URL the client can use to fetch the artifact."""

    _, identity = deps
    job = repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found or expired")
    if job.identity != identity:
        raise HTTPException(status_code=403, detail="job belongs to another identity")
    if job.result is None or not job.artifact_path:
        raise HTTPException(status_code=409, detail="job not finished")

    filename = job.result.filename
    url, expires_at = signed_download_url(
        settings,
        job_id=job_id,
        filename=filename,
        identity=identity,
    )
    return {"download_url": url, "expires_at": expires_at, "filename": filename}


@router.get("/api/v1/jobs/{job_id}/file/{filename}", tags=["jobs"])
def download_artifact(
    job_id: str,
    filename: str,
    token: str = Query(..., description="Short-lived JWT minted by the API"),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Public endpoint, but only with a valid signed token."""

    try:
        verify_download_token(settings, token, job_id=job_id, filename=filename)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    storage = get_storage()
    try:
        path = storage.resolve_safe(job_id, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=410, detail="artifact gone (expired or cleaned up)")

    media_type, _ = mimetypes.guess_type(filename)
    return FileResponse(
        path=str(path),
        media_type=media_type or "application/octet-stream",
        filename=filename,
    )
