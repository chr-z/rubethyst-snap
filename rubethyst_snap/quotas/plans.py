from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..api.settings import Settings


class PlanName(str, Enum):
    FREE = "free"
    PRO = "pro"


@dataclass(frozen=True, slots=True)
class Plan:
    name: PlanName
    max_duration_seconds: int
    max_filesize_mb: int
    max_height: int
    concurrency: int
    rate_per_hour: int
    retention_hours: int
    queue: str
    allowed_presets: frozenset[str]


def _free_plan(settings: Settings) -> Plan:
    return Plan(
        name=PlanName.FREE,
        max_duration_seconds=settings.free_max_duration_seconds,
        max_filesize_mb=settings.free_max_filesize_mb,
        max_height=settings.free_max_height,
        concurrency=settings.free_concurrency,
        rate_per_hour=settings.free_rate_per_hour,
        retention_hours=settings.artifact_ttl_hours_free,
        queue=settings.celery_default_queue,
        allowed_presets=frozenset({"720p", "audio", "mp3"}),
    )


def _pro_plan(settings: Settings) -> Plan:
    return Plan(
        name=PlanName.PRO,
        max_duration_seconds=settings.pro_max_duration_seconds,
        max_filesize_mb=settings.pro_max_filesize_mb,
        max_height=settings.pro_max_height,
        concurrency=settings.pro_concurrency,
        rate_per_hour=settings.pro_rate_per_hour,
        retention_hours=settings.artifact_ttl_hours_pro,
        queue=settings.celery_pro_queue,
        allowed_presets=frozenset({"smart_1080", "1080p", "720p", "best", "mp4", "audio", "mp3"}),
    )


def PLANS(settings: Settings) -> dict[PlanName, Plan]:
    return {
        PlanName.FREE: _free_plan(settings),
        PlanName.PRO: _pro_plan(settings),
    }


def plan_for(plan_name: str | PlanName, settings: Settings) -> Plan:
    name = PlanName(plan_name) if isinstance(plan_name, str) else plan_name
    return PLANS(settings)[name]
