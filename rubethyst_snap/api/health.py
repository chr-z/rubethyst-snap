from __future__ import annotations

import shutil
from pathlib import Path

from redis import Redis
from redis.exceptions import RedisError
import yt_dlp.version

from .schemas import HealthResponse
from .settings import Settings


def build_health_response(settings: Settings, redis: Redis) -> HealthResponse:
    try:
        redis.ping()
        redis_status = "ok"
    except RedisError as exc:
        redis_status = f"fail: {exc}"

    target = Path(settings.downloads_dir)
    target.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(str(target))
    percent = (usage.used / usage.total * 100) if usage.total else 0.0

    return HealthResponse(
        status="ok" if redis_status == "ok" else "degraded",
        redis=redis_status,
        yt_dlp_version=yt_dlp.version.__version__,
        disk_total_bytes=usage.total,
        disk_used_bytes=usage.used,
        disk_free_bytes=usage.free,
        disk_percent_used=round(percent, 2),
    )
