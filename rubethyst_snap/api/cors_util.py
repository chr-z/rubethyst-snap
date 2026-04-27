"""CORS origins for browser clients (Next.js, etc.)."""

from __future__ import annotations

from .settings import Settings


def effective_cors_origins(settings: Settings) -> list[str]:
    """Merge configured origins with dev defaults when the API is clearly local.

    Browsers treat ``http://localhost:3000`` and ``http://127.0.0.1:3000`` as
    different origins; both must be allowed or ``fetch`` fails with
    ``TypeError: Failed to fetch``.
    """

    configured = [o.strip() for o in settings.cors_origins if o and o.strip()]
    pub = (settings.public_base_url or "").lower()
    dev_api = (
        "localhost" in pub
        or "127.0.0.1" in pub
        or "[::1]" in pub
    )
    if dev_api:
        dev_frontends = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://[::1]:3000",
        ]
        merged = dev_frontends + configured
    else:
        merged = configured
    return list(dict.fromkeys(merged))
