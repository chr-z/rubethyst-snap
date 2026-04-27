#!/usr/bin/env bash
# Sobe só o Redis (docker-compose.yml na raiz do repo).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
exec docker compose up -d
