"""Local filesystem storage for job artifacts.

Production runs on a single Oracle VM with a shared volume between the
worker (read/write) and the API (read-only for streaming). No object
storage is involved; downloads are served by the API after validating a
short-lived signed token.
"""

from .local import LocalArtifactStorage

__all__ = ["LocalArtifactStorage"]
