from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..api.schemas import Job, JobResult
from ..core.progress import ProgressEvent


@runtime_checkable
class JobRepository(Protocol):
    """Persistence contract for jobs.

    Implementations are responsible for their own TTL/expiration; the
    Redis backend uses ``EX`` matching the plan's retention, while a
    future SQLite/Postgres backend would hold history indefinitely and
    let the cleanup task decide what to expose to clients.
    """

    def create(self, job: Job) -> Job: ...

    def get(self, job_id: str) -> Optional[Job]: ...

    def update_progress(self, job_id: str, event: ProgressEvent) -> None: ...

    def attach_metadata(
        self,
        job_id: str,
        *,
        title: str,
        duration: int | None,
        extractor: str,
        artifact_path: str | None = None,
    ) -> None: ...

    def finish(self, job_id: str, result: JobResult) -> None: ...

    def fail(self, job_id: str, error: str) -> None: ...

    def list_active(self) -> list[Job]: ...
