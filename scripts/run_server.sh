#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
read -r HOST PORT < <(
  cd "$ROOT"
  uv run python -c 'import sys; sys.path.insert(0, "cli"); from config import load_config; c=load_config().server; print(c.host, c.port)'
)
cd "$ROOT"
exec uv run uvicorn server.main:app --host "$HOST" --port "$PORT"
