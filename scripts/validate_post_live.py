"""Smoke test for YouTube post-live VOD handling.

Run against a fresh-from-live URL to confirm yt-dlp + our extractor
tuning still produce a usable file. Intended for manual / CI-cron use.

Usage::

    python scripts/validate_post_live.py <youtube_url> [--preset smart_1080]

Exit code is 0 on success, 1 if metadata or download fails.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from rubethyst_snap.core import download, extract_metadata
from rubethyst_snap.core.exceptions import RubethystError
from rubethyst_snap.core.youtube_options import is_youtube


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--preset", default="smart_1080")
    parser.add_argument("--max-duration", type=int, default=600)
    args = parser.parse_args()

    try:
        meta = extract_metadata(args.url)
    except RubethystError as exc:
        print(f"[meta] FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"[meta] title={meta.title!r} extractor={meta.extractor} "
          f"duration={meta.duration_seconds}s was_live={meta.was_live}")
    if not is_youtube(meta.extractor):
        print("[meta] WARN: not a YouTube extractor, post-live tuning is a no-op")

    with tempfile.TemporaryDirectory(prefix="snap-validate-") as tmp:
        out = Path(tmp)
        try:
            result = download(
                args.url,
                output_dir=out,
                preset=args.preset,
                max_duration_seconds=args.max_duration,
            )
        except RubethystError as exc:
            print(f"[download] FAIL: {exc}", file=sys.stderr)
            return 1

        size_mb = result.bytes_written / (1024 * 1024)
        print(f"[download] OK: {result.output_path.name} "
              f"({size_mb:.1f} MB, container={result.container})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
