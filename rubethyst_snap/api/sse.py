"""Server-Sent Events bridge from Redis Pub/Sub to HTTP clients."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import redis.asyncio as aioredis

from ..core.progress import ProgressEvent, ProgressStatus

PROGRESS_CHANNEL_FMT = "snap:job:{job_id}:progress"


def progress_channel(job_id: str) -> str:
    return PROGRESS_CHANNEL_FMT.format(job_id=job_id)


async def progress_event_stream(
    redis_url: str,
    job_id: str,
    *,
    initial_event: ProgressEvent | None = None,
    keepalive_seconds: float = 15.0,
) -> AsyncIterator[dict[str, str]]:
    """Yield SSE-shaped dicts (``event``, ``data``) for one job.

    The generator subscribes to the job's Pub/Sub channel and emits a
    keepalive comment every ``keepalive_seconds`` so reverse proxies do
    not drop idle connections.
    """

    if initial_event is not None:
        yield {"event": "progress", "data": json.dumps(initial_event.to_dict())}
        if initial_event.status in {ProgressStatus.FINISHED, ProgressStatus.ERROR}:
            return

    client: aioredis.Redis = aioredis.from_url(redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(progress_channel(job_id))
    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=keepalive_seconds,
                )
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}
                continue

            if message is None:
                continue

            data = message.get("data")
            if not data:
                continue

            yield {"event": "progress", "data": data if isinstance(data, str) else data.decode()}

            try:
                payload = json.loads(data)
            except (TypeError, ValueError):
                continue
            status = payload.get("status")
            if status in {ProgressStatus.FINISHED.value, ProgressStatus.ERROR.value}:
                return
    finally:
        try:
            await pubsub.unsubscribe(progress_channel(job_id))
            await pubsub.close()
        finally:
            await client.aclose()


def publish_progress_sync(redis, job_id: str, event: ProgressEvent) -> None:
    """Used by the worker (sync redis client) after each progress update."""

    redis.publish(progress_channel(job_id), json.dumps(event.to_dict()))
