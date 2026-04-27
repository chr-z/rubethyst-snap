from __future__ import annotations

import hashlib
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, Request, status
from redis import Redis

from ..jobs.redis_repo import RedisJobRepository
from ..quotas.plans import Plan, PlanName, plan_for
from ..storage.local import LocalArtifactStorage
from .settings import Settings, get_settings


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=False)


@lru_cache(maxsize=1)
def get_storage() -> LocalArtifactStorage:
    settings = get_settings()
    return LocalArtifactStorage(base_dir=settings.downloads_dir)


def get_repository(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> RedisJobRepository:
    plan: Plan = request.state.plan if hasattr(request.state, "plan") else plan_for(
        PlanName.FREE, settings
    )
    return RedisJobRepository(get_redis(), ttl_seconds=plan.retention_hours * 3600)


def resolve_plan(
    x_plan: str | None = Header(default=None, alias="X-Plan"),
    settings: Settings = Depends(get_settings),
) -> Plan:
    raw = (x_plan or "free").lower().strip()
    try:
        name = PlanName(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"unknown plan {raw!r}")
    return plan_for(name, settings)


def resolve_identity(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """Identity used for quotas and signed URLs.

    MVP: API key when supplied, otherwise SHA-256 of the client IP. We
    intentionally avoid raw IPs in keys to keep them out of logs.
    """

    if x_api_key:
        return f"key:{x_api_key.strip()[:64]}"
    client = request.client.host if request.client else "0.0.0.0"
    digest = hashlib.sha256(client.encode("utf-8")).hexdigest()[:16]
    return f"ip:{digest}"


def attach_request_state(
    request: Request,
    plan: Plan = Depends(resolve_plan),
    identity: str = Depends(resolve_identity),
) -> tuple[Plan, str]:
    request.state.plan = plan
    request.state.identity = identity
    return plan, identity


def require_plan_and_identity(
    deps: tuple[Plan, str] = Depends(attach_request_state),
) -> tuple[Plan, str]:
    return deps


def enforce_rate_limit(
    deps: tuple[Plan, str] = Depends(require_plan_and_identity),
) -> tuple[Plan, str]:
    from ..quotas.rate_limit import check_rate_limit

    plan, identity = deps
    decision = check_rate_limit(get_redis(), identity, limit_per_hour=plan.rate_per_hour)
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "rate limit exceeded",
                "limit": decision.limit,
                "count": decision.count,
                "retry_after_seconds": decision.retry_after_seconds,
            },
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
    return plan, identity
