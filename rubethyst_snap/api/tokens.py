from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from .settings import Settings


_AUDIENCE = "rubethyst-snap-download"


@dataclass(slots=True)
class DownloadToken:
    token: str
    expires_at: datetime


def issue_download_token(
    settings: Settings,
    *,
    job_id: str,
    filename: str,
    identity: str,
) -> DownloadToken:
    """Mint a short-lived JWT for one job artifact.

    The token binds the job id, the exact filename and the requesting
    identity. Anyone re-sharing the URL has to re-share the token, which
    expires inside the configured TTL (default 1h).
    """

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.download_token_ttl_seconds)
    payload = {
        "sub": job_id,
        "filename": filename,
        "identity": identity,
        "aud": _AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.download_token_secret, algorithm="HS256")
    return DownloadToken(token=token, expires_at=expires_at)


def verify_download_token(settings: Settings, token: str, *, job_id: str, filename: str) -> str:
    """Return the embedded identity if the token is valid, else raise."""

    try:
        payload = jwt.decode(
            token,
            settings.download_token_secret,
            algorithms=["HS256"],
            audience=_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise PermissionError(f"invalid token: {exc}") from exc

    if payload.get("sub") != job_id:
        raise PermissionError("token job mismatch")
    if payload.get("filename") != filename:
        raise PermissionError("token filename mismatch")
    return str(payload.get("identity") or "anonymous")


def signed_download_url(
    settings: Settings,
    *,
    job_id: str,
    filename: str,
    identity: str,
) -> tuple[str, datetime]:
    minted = issue_download_token(settings, job_id=job_id, filename=filename, identity=identity)
    base = settings.public_base_url.rstrip("/")
    url = f"{base}/api/v1/jobs/{job_id}/file/{filename}?token={minted.token}"
    return url, minted.expires_at
