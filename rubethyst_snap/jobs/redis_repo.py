from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from redis import Redis

from ..api.schemas import Job, JobProgress, JobResult
from ..core.progress import ProgressEvent, ProgressStatus


_KEY_PREFIX = "snap:job:"
_INDEX_KEY = "snap:jobs:index"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _key(job_id: str) -> str:
    return f"{_KEY_PREFIX}{job_id}"


class RedisJobRepository:
    """Redis-backed implementation of :class:`JobRepository`.

    Each job is one JSON blob keyed by id; the index set holds active
    job ids so the cleanup task can iterate without ``KEYS``.
    """

    def __init__(self, redis: Redis, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def create(self, job: Job) -> Job:
        self._save(job)
        self._redis.sadd(_INDEX_KEY, job.id)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        raw = self._redis.get(_key(job_id))
        if raw is None:
            return None
        return Job.model_validate_json(raw)

    def update_progress(self, job_id: str, event: ProgressEvent) -> None:
        job = self.get(job_id)
        if job is None:
            return
        job.progress = JobProgress(
            status=event.status,
            percent=event.percent,
            downloaded_bytes=event.downloaded_bytes,
            total_bytes=event.total_bytes,
            speed_bps=event.speed_bps,
            eta_seconds=event.eta_seconds,
            message=event.message,
        )
        job.updated_at = _now()
        self._save(job)

    def attach_metadata(
        self,
        job_id: str,
        *,
        title: str,
        duration: int | None,
        extractor: str,
        artifact_path: str | None = None,
    ) -> None:
        job = self.get(job_id)
        if job is None:
            return
        job.title = title
        job.duration_seconds = duration
        job.extractor = extractor
        if artifact_path is not None:
            job.artifact_path = artifact_path
        job.updated_at = _now()
        self._save(job)

    def finish(self, job_id: str, result: JobResult) -> None:
        job = self.get(job_id)
        if job is None:
            return
        job.result = result
        job.progress = JobProgress(status=ProgressStatus.FINISHED, percent=100.0)
        job.updated_at = _now()
        self._save(job)

    def fail(self, job_id: str, error: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        job.error = error
        job.progress = JobProgress(status=ProgressStatus.ERROR, message=error)
        job.updated_at = _now()
        self._save(job)
        self._redis.srem(_INDEX_KEY, job.id)

    def list_active(self) -> list[Job]:
        ids = [i.decode() if isinstance(i, bytes) else i for i in self._redis.smembers(_INDEX_KEY)]
        out: list[Job] = []
        stale: list[str] = []
        for jid in ids:
            job = self.get(jid)
            if job is None:
                stale.append(jid)
                continue
            out.append(job)
        if stale:
            self._redis.srem(_INDEX_KEY, *stale)
        return out

    def _save(self, job: Job) -> None:
        payload = job.model_dump_json()
        self._redis.set(_key(job.id), payload, ex=self._ttl)
