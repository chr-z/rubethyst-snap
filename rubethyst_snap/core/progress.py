from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional


class ProgressStatus(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    DOWNLOADING = "downloading"
    MERGING = "merging"
    POSTPROCESSING = "postprocessing"
    UPLOADING = "uploading"
    FINISHED = "finished"
    ERROR = "error"
    RETRYING = "retrying"


@dataclass(slots=True)
class ProgressEvent:
    """A single progress observation emitted by the engine."""

    status: ProgressStatus
    percent: Optional[float] = None
    downloaded_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    speed_bps: Optional[float] = None
    eta_seconds: Optional[int] = None
    message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "percent": self.percent,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "speed_bps": self.speed_bps,
            "eta_seconds": self.eta_seconds,
            "message": self.message,
        }

    @classmethod
    def from_yt_dlp(cls, hook: dict[str, Any]) -> "ProgressEvent":
        raw_status = hook.get("status", "downloading")
        status = {
            "downloading": ProgressStatus.DOWNLOADING,
            "finished": ProgressStatus.MERGING,
            "error": ProgressStatus.ERROR,
        }.get(raw_status, ProgressStatus.DOWNLOADING)

        downloaded = hook.get("downloaded_bytes")
        total = hook.get("total_bytes") or hook.get("total_bytes_estimate")
        percent = (downloaded / total * 100) if downloaded and total else None

        return cls(
            status=status,
            percent=percent,
            downloaded_bytes=downloaded,
            total_bytes=total,
            speed_bps=hook.get("speed"),
            eta_seconds=hook.get("eta"),
        )


ProgressCallback = Callable[[ProgressEvent], None]
"""Function that receives progress events.

The callback runs inside yt-dlp's hook thread; do NOT touch UI toolkits
or per-request state directly. Forward to a thread-safe queue, an
asyncio loop, or a Redis Pub/Sub channel.
"""
