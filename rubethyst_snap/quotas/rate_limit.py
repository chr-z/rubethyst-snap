from __future__ import annotations

import time
from dataclasses import dataclass

from redis import Redis


_KEY_FMT = "snap:rate:{identity}:{window}"


@dataclass(slots=True)
class RateLimitDecision:
    allowed: bool
    count: int
    limit: int
    retry_after_seconds: int


def check_rate_limit(
    redis: Redis,
    identity: str,
    *,
    limit_per_hour: int,
    window_seconds: int = 3600,
) -> RateLimitDecision:
    """Fixed-window rate limit using a single ``INCR`` + ``EXPIRE``.

    Coarser than a sliding window but cheap and easy to reason about;
    good enough for per-user/per-IP throttling at the API edge.
    """

    now = int(time.time())
    window_id = now // window_seconds
    key = _KEY_FMT.format(identity=identity, window=window_id)

    pipe = redis.pipeline()
    pipe.incr(key, 1)
    pipe.expire(key, window_seconds)
    count, _ = pipe.execute()
    count = int(count)

    retry_after = window_seconds - (now % window_seconds) if count > limit_per_hour else 0
    return RateLimitDecision(
        allowed=count <= limit_per_hour,
        count=count,
        limit=limit_per_hour,
        retry_after_seconds=retry_after,
    )
