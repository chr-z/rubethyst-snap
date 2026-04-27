"""YouTube-specific tuning.

Recently-ended live VODs sometimes return formats that trigger heavy
re-processing on the server side (long ``post-live manifestless`` waits,
slow fragment fetches). Switching the player client to ``android`` /
``tv_embedded`` and disabling DASH manifests usually bypasses that path
and goes straight to the regular HLS/DASH streams.

Notes
-----
* These options are extractor-specific; they apply only when the URL is
  resolved by the youtube extractor. The downloader checks the extractor
  before merging.
* This is a moving target and yt-dlp updates frequently; the
  ``scripts/validate_post_live.py`` smoke-test exists to detect
  regressions as the upstream library changes.
"""

from __future__ import annotations

from typing import Any


def youtube_extractor_args() -> dict[str, Any]:
    # NOTE: do NOT hard-pin ``player_client`` here. yt-dlp's built-in defaults
    # rotate as YouTube breaks things; forcing a subset historically gave us
    # either 360p-only (android without PoToken) or empty format lists
    # (web-only sometimes returns storyboards only via ``process=False``).
    # Keep this callable available for future per-extractor tweaks, but
    # return an empty dict so the default client rotation is used.
    return {"youtube": {}}


def is_youtube(extractor: str | None) -> bool:
    if not extractor:
        return False
    return extractor.lower().startswith("youtube")


def url_looks_like_youtube(url: str) -> bool:
    """Heuristic before yt-dlp resolves the extractor (needed for live URLs)."""

    lower = url.strip().lower()
    if "youtube.com/" in lower:
        return True
    if "youtu.be/" in lower:
        return True
    if "m.youtube.com" in lower:
        return True
    if "music.youtube.com" in lower:
        return True
    return False


def apply_youtube_tuning(
    opts: dict[str, Any],
    *,
    extractor: str | None = None,
    url: str | None = None,
) -> None:
    if not (is_youtube(extractor) or (url and url_looks_like_youtube(url))):
        return
    yt_new = youtube_extractor_args().get("youtube") or {}
    if yt_new:
        existing = opts.get("extractor_args") or {}
        if not isinstance(existing, dict):
            existing = {}
        yt_old = (
            existing.get("youtube")
            if isinstance(existing.get("youtube"), dict)
            else {}
        )
        opts["extractor_args"] = {
            **existing,
            "youtube": {**yt_old, **yt_new},
        }
    opts.setdefault("hls_prefer_native", True)
    opts.setdefault("socket_timeout", 90)
