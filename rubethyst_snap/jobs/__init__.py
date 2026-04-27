"""Job persistence layer.

Today the production implementation uses Redis hashes (one JSON blob
per job, TTL aligned with the artifact retention). The repository
interface in :mod:`repository` lets us slot in a SQLite or Postgres
backend later for durable history and billing without rewriting the
API or worker code.
"""

from .repository import JobRepository
from .redis_repo import RedisJobRepository

__all__ = ["JobRepository", "RedisJobRepository"]
