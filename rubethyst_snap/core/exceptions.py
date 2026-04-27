class RubethystError(Exception):
    """Base class for all Rubethyst Snap errors."""


class UnsupportedURLError(RubethystError):
    """Raised when yt-dlp has no extractor for the supplied URL."""


class MetadataError(RubethystError):
    """Raised when metadata extraction fails."""


class DownloadError(RubethystError):
    """Raised when the download/merge pipeline fails."""


class LimitExceededError(RubethystError):
    """Raised when a job violates a configured limit (duration, size, plan)."""
