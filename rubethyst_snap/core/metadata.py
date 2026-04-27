from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YDLDownloadError

from .exceptions import MetadataError, UnsupportedURLError
from .youtube_options import apply_youtube_tuning


@dataclass(slots=True)
class FormatSummary:
    """A trimmed view of a yt-dlp format entry, safe to expose over HTTP."""

    format_id: str
    ext: Optional[str]
    height: Optional[int]
    width: Optional[int]
    fps: Optional[float]
    vcodec: Optional[str]
    acodec: Optional[str]
    tbr: Optional[float]
    vbr: Optional[float]
    abr: Optional[float]
    filesize: Optional[int]
    note: Optional[str]

    @classmethod
    def from_info(cls, fmt: dict[str, Any]) -> "FormatSummary":
        return cls(
            format_id=str(fmt.get("format_id") or ""),
            ext=fmt.get("ext"),
            height=fmt.get("height"),
            width=fmt.get("width"),
            fps=fmt.get("fps"),
            vcodec=None if fmt.get("vcodec") in (None, "none") else fmt.get("vcodec"),
            acodec=None if fmt.get("acodec") in (None, "none") else fmt.get("acodec"),
            tbr=fmt.get("tbr"),
            vbr=fmt.get("vbr"),
            abr=fmt.get("abr"),
            filesize=fmt.get("filesize") or fmt.get("filesize_approx"),
            note=fmt.get("format_note"),
        )


@dataclass(slots=True)
class VideoMetadata:
    """Serializable subset of yt-dlp's ``info_dict``."""

    id: str
    title: str
    extractor: str
    webpage_url: str
    duration_seconds: Optional[int]
    uploader: Optional[str]
    thumbnail: Optional[str]
    is_live: bool
    was_live: bool
    formats: list[FormatSummary] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_info(cls, info: dict[str, Any]) -> "VideoMetadata":
        formats_raw = info.get("formats") or []
        formats = [FormatSummary.from_info(f) for f in formats_raw if f]
        return cls(
            id=str(info.get("id") or ""),
            title=info.get("title") or "(untitled)",
            extractor=info.get("extractor") or info.get("extractor_key") or "generic",
            webpage_url=info.get("webpage_url") or info.get("original_url") or "",
            duration_seconds=info.get("duration"),
            uploader=info.get("uploader") or info.get("channel"),
            thumbnail=info.get("thumbnail"),
            is_live=bool(info.get("is_live")),
            was_live=bool(info.get("was_live")),
            formats=formats,
            raw=info,
        )


def extract_metadata(url: str, *, cookies_path: str | None = None) -> VideoMetadata:
    """Fetch metadata without downloading the media."""

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    if cookies_path:
        opts["cookiefile"] = cookies_path
    apply_youtube_tuning(opts, url=url)

    # ``process=False`` skips format selection (which can fail with "Requested
    # format is not available" on YouTube when the default selector can't be
    # resolved against the currently-exposed client streams). We only care
    # about raw metadata + format list here, so selection is irrelevant.
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False, process=False)
    except YDLDownloadError as exc:
        message = str(exc).lower()
        if "unsupported url" in message or "no video" in message:
            raise UnsupportedURLError(str(exc)) from exc
        raise MetadataError(str(exc)) from exc

    if info is None:
        raise MetadataError("yt-dlp returned no metadata")

    if "entries" in info and info.get("entries"):
        entries = info["entries"]
        if hasattr(entries, "__iter__") and not isinstance(entries, (list, tuple)):
            entries = list(entries)
        info = next((e for e in entries if e), info)

    return VideoMetadata.from_info(info)
