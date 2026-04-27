from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration loaded from environment variables.

    All names are prefixed with ``RUBETHYST_`` so they don't collide with
    the host environment in shared deployments.
    """

    model_config = SettingsConfigDict(
        env_prefix="RUBETHYST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"

    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    celery_default_queue: str = "snap.default"
    celery_pro_queue: str = "snap.pro"

    downloads_dir: str = "/data/downloads"
    workdir_inside_downloads: bool = True

    public_base_url: str = "http://localhost:8000"
    download_token_secret: str = "change-me-in-production"
    download_token_ttl_seconds: int = Field(default=3600, ge=60, le=24 * 3600)

    artifact_ttl_hours_free: int = Field(default=6, ge=1, le=24 * 30)
    artifact_ttl_hours_pro: int = Field(default=48, ge=1, le=24 * 30)

    cemetery_orphan_age_hours: int = Field(default=24, ge=1)
    cleanup_interval_seconds: int = Field(default=900, ge=60)
    cemetery_interval_seconds: int = Field(default=3600, ge=60)

    free_max_duration_seconds: int = Field(default=15 * 60, ge=60)
    free_max_filesize_mb: int = Field(default=1024, ge=1)
    free_max_height: int = Field(default=720, ge=144)
    free_concurrency: int = Field(default=1, ge=1)
    free_rate_per_hour: int = Field(default=10, ge=1)

    pro_max_duration_seconds: int = Field(default=12 * 3600, ge=60)
    pro_max_filesize_mb: int = Field(default=8192, ge=1)
    pro_max_height: int = Field(default=2160, ge=144)
    pro_concurrency: int = Field(default=3, ge=1)
    pro_rate_per_hour: int = Field(default=120, ge=1)

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    cors_origins: list[str] = Field(default_factory=list)

    @property
    def effective_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def effective_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
