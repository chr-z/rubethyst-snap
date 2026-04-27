from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YDLDownloadError

from .exceptions import DownloadError, LimitExceededError, UnsupportedURLError
from .format_selection import SMART_FORMAT_SORT
from .formats import FormatPreset, resolve_preset
from .metadata import VideoMetadata
from .progress import ProgressCallback, ProgressEvent, ProgressStatus
from .youtube_options import apply_youtube_tuning


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, *, max_length: int = 120) -> str:
    cleaned = _INVALID_FILENAME_CHARS.sub("_", name).strip(" .")
    if not cleaned:
        cleaned = "video"
    return cleaned[:max_length]


@dataclass(slots=True)
class DownloadResult:
    output_path: Path
    metadata: VideoMetadata
    bytes_written: int
    container: str


def _emit(callback: Optional[ProgressCallback], event: ProgressEvent) -> None:
    if callback is None:
        return
    try:
        callback(event)
    except Exception:
        pass


def _probe(url: str, cookies_path: str | None) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    if cookies_path:
        opts["cookiefile"] = cookies_path

    apply_youtube_tuning(opts, url=url)

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except YDLDownloadError as exc:
        if "unsupported url" in str(exc).lower():
            raise UnsupportedURLError(str(exc)) from exc
        raise DownloadError(str(exc)) from exc

    if info is None:
        raise DownloadError("yt-dlp returned no metadata")
    if "entries" in info and info.get("entries"):
        info = next((e for e in info["entries"] if e), info)
    return info


def download(
    url: str,
    output_dir: str | os.PathLike[str],
    *,
    preset: str | FormatPreset = "smart_1080",
    progress: Optional[ProgressCallback] = None,
    cookies_path: str | None = None,
    max_duration_seconds: int | None = None,
    max_filesize_bytes: int | None = None,
    overwrite: bool = False,
    apply_smart_sort: bool = True,
    format_id: str | None = None,
) -> DownloadResult:
    """Download ``url`` into ``output_dir`` and return the resulting artifact.

    ``progress`` runs inside yt-dlp's hook thread; dispatch updates to
    your event loop / Pub/Sub bus from there.
    """

    preset_obj = resolve_preset(preset)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _emit(progress, ProgressEvent(status=ProgressStatus.EXTRACTING))

    info = _probe(url, cookies_path)
    metadata = VideoMetadata.from_info(info)

    if max_duration_seconds and metadata.duration_seconds:
        if metadata.duration_seconds > max_duration_seconds:
            raise LimitExceededError(
                f"Video duration {metadata.duration_seconds}s exceeds limit "
                f"{max_duration_seconds}s"
            )

    safe_title = sanitize_filename(metadata.title)
    outtmpl = str(output_dir / f"{safe_title}.%(ext)s")

    def hook(raw: dict[str, Any]) -> None:
        _emit(progress, ProgressEvent.from_yt_dlp(raw))

    def postprocessor_hook(raw: dict[str, Any]) -> None:
        if raw.get("status") == "started":
            _emit(progress, ProgressEvent(
                status=ProgressStatus.POSTPROCESSING,
                message=raw.get("postprocessor"),
            ))

    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "overwrites": overwrite,
        "progress_hooks": [hook],
        "postprocessor_hooks": [postprocessor_hook],
        "concurrent_fragment_downloads": 4,
        "retries": 3,
        "fragment_retries": 3,
    }
    ydl_opts.update(preset_obj.to_ydl_opts())
    if apply_smart_sort and "format_sort" not in ydl_opts:
        ydl_opts["format_sort"] = list(SMART_FORMAT_SORT)
    if format_id:
        ydl_opts["format"] = f"{format_id}+bestaudio/{format_id}"
        ydl_opts.setdefault("merge_output_format", "mp4")
    if cookies_path:
        ydl_opts["cookiefile"] = cookies_path
    if max_filesize_bytes:
        ydl_opts["max_filesize"] = max_filesize_bytes

    apply_youtube_tuning(ydl_opts, extractor=metadata.extractor)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            result_info = ydl.extract_info(url, download=True)
    except YDLDownloadError as exc:
        raise DownloadError(str(exc)) from exc

    if result_info is None:
        raise DownloadError("Download finished without producing a file")
    if "entries" in result_info and result_info.get("entries"):
        result_info = next((e for e in result_info["entries"] if e), result_info)

    final_path = _resolve_final_path(result_info, output_dir, safe_title)
    if not final_path.exists():
        raise DownloadError(f"Expected output {final_path} was not created")

    bytes_written = final_path.stat().st_size
    _emit(progress, ProgressEvent(
        status=ProgressStatus.FINISHED,
        percent=100.0,
        downloaded_bytes=bytes_written,
        total_bytes=bytes_written,
    ))

    return DownloadResult(
        output_path=final_path,
        metadata=metadata,
        bytes_written=bytes_written,
        container=final_path.suffix.lstrip("."),
    )


def _resolve_final_path(info: dict[str, Any], output_dir: Path, safe_title: str) -> Path:
    """Find the artifact yt-dlp actually wrote.

    yt-dlp may rewrite the extension after merging or postprocessing, so
    trusting our own template is unsafe.
    """

    requested = info.get("requested_downloads") or []
    for entry in requested:
        path = entry.get("filepath") or entry.get("filename")
        if path:
            return Path(path)

    direct = info.get("filepath") or info.get("_filename")
    if direct:
        return Path(direct)

    candidates = sorted(
        output_dir.glob(f"{safe_title}.*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]

    raise DownloadError("Could not locate downloaded file")
