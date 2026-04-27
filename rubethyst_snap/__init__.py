"""Rubethyst Snap: motor multi-plataforma de download de vídeo (Rubethyst Lab)."""

from .core import (
    DownloadResult,
    ProgressEvent,
    ProgressStatus,
    RubethystError,
    VideoMetadata,
    download,
    extract_metadata,
)

__version__ = "0.1.0"

__all__ = [
    "DownloadResult",
    "ProgressEvent",
    "ProgressStatus",
    "RubethystError",
    "VideoMetadata",
    "__version__",
    "download",
    "extract_metadata",
]
