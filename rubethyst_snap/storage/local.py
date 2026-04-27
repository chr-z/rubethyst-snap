from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class LocalArtifactStorage:
    base_dir: Path

    def __post_init__(self) -> None:
        self.base_dir = Path(self.base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def workdir(self, job_id: str) -> Path:
        path = self.base_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def artifact_path(self, job_id: str, filename: str) -> Path:
        return self.workdir(job_id) / filename

    def relative_path(self, absolute: Path) -> Path:
        return absolute.relative_to(self.base_dir)

    def resolve_safe(self, job_id: str, filename: str) -> Path:
        """Return a path inside the job directory, rejecting traversal.

        Anything that resolves outside ``base_dir/{job_id}`` raises
        ``ValueError``; this is the only public way to materialize a
        client-supplied filename into a real path.
        """

        candidate = (self.workdir(job_id) / filename).resolve()
        root = self.workdir(job_id).resolve()
        if root not in candidate.parents and candidate != root:
            raise ValueError("path escapes job directory")
        return candidate
