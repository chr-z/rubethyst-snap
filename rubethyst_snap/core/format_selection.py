"""Smart format selection helpers.

When the user does not pass a hard preset, we still want to pick the
*best* stream that respects plan limits. yt-dlp already resolves the
``format`` selector, but we can boost decisions with ``format_sort``
(highest bitrate first) and we can also pick a concrete ``format_id``
ourselves when we already have the ``info_dict`` from a prefetch call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass(slots=True)
class FormatChoice:
    video_format_id: str
    audio_format_id: Optional[str]
    height: int
    tbr: float
    container_hint: Optional[str]

    def as_selector(self) -> str:
        if self.audio_format_id:
            return f"{self.video_format_id}+{self.audio_format_id}"
        return self.video_format_id


def _is_video_only(fmt: dict[str, Any]) -> bool:
    return fmt.get("vcodec") not in (None, "none") and fmt.get("acodec") in (None, "none")


def _is_audio_only(fmt: dict[str, Any]) -> bool:
    return fmt.get("acodec") not in (None, "none") and fmt.get("vcodec") in (None, "none")


def _is_progressive(fmt: dict[str, Any]) -> bool:
    return fmt.get("vcodec") not in (None, "none") and fmt.get("acodec") not in (None, "none")


def _bitrate(fmt: dict[str, Any]) -> float:
    return float(
        fmt.get("tbr")
        or (fmt.get("vbr") or 0) + (fmt.get("abr") or 0)
        or 0.0
    )


def pick_best_under_height(
    formats: Iterable[dict[str, Any]],
    *,
    max_height: int = 1080,
) -> Optional[FormatChoice]:
    """Pick the highest-bitrate video stream <= ``max_height``.

    Returns ``None`` if the extractor only exposed unknown shapes; the
    caller should then fall back to a yt-dlp ``format`` selector string.
    """

    formats = list(formats)
    if not formats:
        return None

    videos = [
        f for f in formats
        if _is_video_only(f) and (f.get("height") or 0) <= max_height
    ]
    audios = [f for f in formats if _is_audio_only(f)]

    if videos and audios:
        best_video = max(videos, key=lambda f: (f.get("height") or 0, _bitrate(f)))
        best_audio = max(audios, key=lambda f: _bitrate(f))
        return FormatChoice(
            video_format_id=str(best_video["format_id"]),
            audio_format_id=str(best_audio["format_id"]),
            height=int(best_video.get("height") or 0),
            tbr=_bitrate(best_video) + _bitrate(best_audio),
            container_hint=best_video.get("ext"),
        )

    progressive = [
        f for f in formats
        if _is_progressive(f) and (f.get("height") or 0) <= max_height
    ]
    if progressive:
        best = max(progressive, key=lambda f: (f.get("height") or 0, _bitrate(f)))
        return FormatChoice(
            video_format_id=str(best["format_id"]),
            audio_format_id=None,
            height=int(best.get("height") or 0),
            tbr=_bitrate(best),
            container_hint=best.get("ext"),
        )

    return None


def smart_format_string(max_height: int = 1080) -> str:
    """Pure-string yt-dlp selector when we cannot inspect ``info_dict``."""

    return (
        f"bv*[height<={max_height}]+ba/"
        f"b[height<={max_height}]/"
        "bv*+ba/b"
    )


SMART_FORMAT_SORT: tuple[str, ...] = (
    "res:1080",
    "tbr",
    "vbr",
    "abr",
    "fps",
    "size",
)
