"""Format presets for the download engine.

Presets are deliberately generic so the engine works on every yt-dlp
extractor, not just YouTube. Site-specific stream selection is left to
yt-dlp's resolver, which negotiates the best matching pair.

The ``smart_1080`` preset uses :mod:`format_selection` to inject an
extra ``format_sort`` that prefers the highest-bitrate 1080p stream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FormatPreset:
    name: str
    description: str
    selector: str
    merge_format: str | None = None
    postprocessors: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    format_sort: tuple[str, ...] = field(default_factory=tuple)
    max_height: int | None = None

    def to_ydl_opts(self) -> dict[str, Any]:
        opts: dict[str, Any] = {"format": self.selector}
        if self.merge_format:
            opts["merge_output_format"] = self.merge_format
        if self.postprocessors:
            opts["postprocessors"] = [dict(pp) for pp in self.postprocessors]
        if self.format_sort:
            opts["format_sort"] = list(self.format_sort)
        return opts


PRESETS: dict[str, FormatPreset] = {
    "best": FormatPreset(
        name="best",
        description="Best available video + best audio, muxed (mkv/mp4/webm).",
        selector="bv*+ba/b",
    ),
    "mp4": FormatPreset(
        name="mp4",
        description="Prefer mp4 video and m4a audio, fall back to anything muxed to mp4.",
        selector="bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        merge_format="mp4",
    ),
    "smart_1080": FormatPreset(
        name="smart_1080",
        description="Highest-bitrate 1080p video + best audio (smart selector).",
        selector="bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        merge_format="mp4",
        format_sort=("res:1080", "tbr", "vbr", "abr", "fps", "size"),
        max_height=1080,
    ),
    "1080p": FormatPreset(
        name="1080p",
        description="Cap video at 1080p, prefer mp4 container.",
        selector="bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]",
        merge_format="mp4",
        max_height=1080,
    ),
    "720p": FormatPreset(
        name="720p",
        description="Cap video at 720p, prefer mp4 container (Free plan default).",
        selector="bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]",
        merge_format="mp4",
        max_height=720,
    ),
    "audio": FormatPreset(
        name="audio",
        description="Audio-only, original codec (m4a/opus/etc).",
        selector="bestaudio/best",
    ),
    "mp3": FormatPreset(
        name="mp3",
        description="Audio-only, transcoded to 192kbps mp3.",
        selector="bestaudio/best",
        postprocessors=(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
        ),
    ),
}


def resolve_preset(name: str | FormatPreset) -> FormatPreset:
    if isinstance(name, FormatPreset):
        return name
    try:
        return PRESETS[name.lower()]
    except KeyError as exc:
        valid = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown format preset {name!r}. Valid: {valid}") from exc
