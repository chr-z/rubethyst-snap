from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl

from ..core.formats import PRESETS
from ..core.progress import ProgressStatus
from ..quotas.plans import PlanName


class JobCreate(BaseModel):
    url: HttpUrl
    preset: str = Field(
        default="smart_1080",
        description=f"One of: {sorted(PRESETS)}",
    )
    format_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional yt-dlp format_id to force (video-only ID; audio will "
            "be picked automatically). Overrides the preset's selector."
        ),
    )


class PreviewRequest(BaseModel):
    url: HttpUrl


class FormatOut(BaseModel):
    format_id: str
    ext: Optional[str] = None
    height: Optional[int] = None
    width: Optional[int] = None
    fps: Optional[float] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    tbr: Optional[float] = None
    vbr: Optional[float] = None
    abr: Optional[float] = None
    filesize: Optional[int] = None
    note: Optional[str] = None


class PreviewResponse(BaseModel):
    title: str
    extractor: str
    duration_seconds: Optional[int] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    is_live: bool = False
    was_live: bool = False
    formats: list[FormatOut] = Field(default_factory=list)


class JobProgress(BaseModel):
    status: ProgressStatus
    percent: Optional[float] = None
    downloaded_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    speed_bps: Optional[float] = None
    eta_seconds: Optional[int] = None
    message: Optional[str] = None


class JobResult(BaseModel):
    download_url: str
    expires_at: datetime
    filename: str
    size_bytes: int
    container: str


class Job(BaseModel):
    id: str
    url: str
    preset: str
    plan: PlanName
    identity: str
    created_at: datetime
    updated_at: datetime
    retention_until: Optional[datetime] = None
    progress: JobProgress
    title: Optional[str] = None
    duration_seconds: Optional[int] = None
    extractor: Optional[str] = None
    artifact_path: Optional[str] = None
    result: Optional[JobResult] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    redis: str
    yt_dlp_version: str
    disk_total_bytes: int
    disk_used_bytes: int
    disk_free_bytes: int
    disk_percent_used: float
    workers_active: Optional[int] = None
