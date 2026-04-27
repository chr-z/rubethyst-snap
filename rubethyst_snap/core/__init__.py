"""Headless download engine built on yt-dlp.

Pure functions, no HTTP server, no UI, no Redis. Consumed by the API
worker, the desktop client, and any future integration.
"""

from .downloader import DownloadResult, download
from .exceptions import (
    DownloadError,
    LimitExceededError,
    MetadataError,
    RubethystError,
    UnsupportedURLError,
)
from .formats import FormatPreset, PRESETS, resolve_preset
from .metadata import FormatSummary, VideoMetadata, extract_metadata
from .progress import ProgressCallback, ProgressEvent, ProgressStatus

__all__ = [
    "DownloadError",
    "DownloadResult",
    "FormatPreset",
    "FormatSummary",
    "LimitExceededError",
    "MetadataError",
    "PRESETS",
    "ProgressCallback",
    "ProgressEvent",
    "ProgressStatus",
    "RubethystError",
    "UnsupportedURLError",
    "VideoMetadata",
    "download",
    "extract_metadata",
    "resolve_preset",
]
