from __future__ import annotations

from dataclasses import dataclass

from redis import Redis


_KEY_FMT = "snap:inflight:{identity}"


@dataclass(slots=True)
class ConcurrencySlot:
    identity: str
    inflight_after: int
    limit: int

    @property
    def acquired(self) -> bool:
        return self.inflight_after <= self.limit


def acquire_slot(redis: Redis, identity: str, *, limit: int, ttl_seconds: int = 86400) -> ConcurrencySlot:
    """Atomically increment the in-flight counter and return its state.

    The TTL is a safety belt: if a worker dies hard and never decrements,
    the counter still expires within a day.
    """

    key = _KEY_FMT.format(identity=identity)
    pipe = redis.pipeline()
    pipe.incr(key, 1)
    pipe.expire(key, ttl_seconds)
    after, _ = pipe.execute()
    return ConcurrencySlot(identity=identity, inflight_after=int(after), limit=limit)


def release_slot(redis: Redis, identity: str) -> int:
    key = _KEY_FMT.format(identity=identity)
    value = redis.decr(key)
    if value is not None and int(value) <= 0:
        redis.delete(key)
        return 0
    return int(value or 0)
