"""Periodic cleanup logic invoked by Celery Beat.

Two passes:

* :func:`sweep_expired` removes artifacts whose ``retention_until`` has
  passed according to the job state. This is the "happy path" cleanup
  driven by the API/worker bookkeeping.
* :func:`sweep_cemetery` walks the storage directory and removes
  *anything* that has not been touched in ``cemetery_orphan_age_hours``
  hours and does not correspond to an active job. This is the safety
  net for failed downloads, killed workers and yt-dlp leftovers
  (``.part``, ``.ytdl``, ``.frag`` and merge temporaries).
"""

from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from redis import Redis

from ..api.settings import Settings
from ..jobs.redis_repo import RedisJobRepository, _INDEX_KEY
from ..storage.local import LocalArtifactStorage

log = logging.getLogger(__name__)

_GARBAGE_SUFFIXES = {".part", ".ytdl", ".frag", ".tmp", ".dl", ".part-frag"}


def sweep_expired(
    *,
    redis: Redis,
    storage: LocalArtifactStorage,
    settings: Settings,
) -> dict:
    repo = RedisJobRepository(redis, ttl_seconds=settings.artifact_ttl_hours_pro * 3600)
    now = datetime.now(timezone.utc)
    deleted_dirs: list[str] = []
    inspected = 0

    for job in repo.list_active():
        inspected += 1
        if job.retention_until and job.retention_until <= now:
            job_dir = storage.workdir(job.id)
            shutil.rmtree(job_dir, ignore_errors=True)
            deleted_dirs.append(job.id)
            redis.srem(_INDEX_KEY, job.id)

    log.info("sweep_expired inspected=%d deleted=%d", inspected, len(deleted_dirs))
    return {"inspected": inspected, "deleted": deleted_dirs}


def sweep_cemetery(
    *,
    redis: Redis,
    storage: LocalArtifactStorage,
    settings: Settings,
) -> dict:
    """Delete orphaned files and empty directories under ``downloads_dir``.

    Rule: file must be older than ``cemetery_orphan_age_hours`` AND not
    belong to a job currently in the active index. Garbage extensions
    (``.part`` etc.) get a shorter grace if they are clearly leftovers.
    """

    base = storage.base_dir
    if not base.exists():
        return {"removed_files": 0, "removed_dirs": 0}

    active_ids = {
        i.decode() if isinstance(i, bytes) else i
        for i in redis.smembers(_INDEX_KEY)
    }
    cutoff = time.time() - settings.cemetery_orphan_age_hours * 3600
    removed_files = 0
    removed_dirs = 0

    for job_dir in sorted(base.iterdir()):
        if not job_dir.is_dir():
            continue

        if job_dir.name in active_ids:
            _purge_garbage(job_dir, cutoff)
            continue

        try:
            mtime = max(p.stat().st_mtime for p in job_dir.rglob("*") if p.is_file())
        except ValueError:
            mtime = job_dir.stat().st_mtime

        if mtime <= cutoff:
            files_count = sum(1 for _ in job_dir.rglob("*") if _.is_file())
            shutil.rmtree(job_dir, ignore_errors=True)
            removed_files += files_count
            removed_dirs += 1

    log.info("sweep_cemetery removed_files=%d removed_dirs=%d", removed_files, removed_dirs)
    return {"removed_files": removed_files, "removed_dirs": removed_dirs}


def _purge_garbage(job_dir: Path, cutoff: float) -> None:
    """Remove obvious yt-dlp leftovers inside an otherwise active job."""

    for path in job_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in _GARBAGE_SUFFIXES and path.stat().st_mtime <= cutoff:
            try:
                path.unlink()
            except OSError:
                pass
