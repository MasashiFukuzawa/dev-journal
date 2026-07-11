#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
TMP="$(mktemp -d)"
PID=""
cleanup() {
  if [ -n "$PID" ]; then kill "$PID" 2>/dev/null || true; fi
  rm -rf "$TMP"
}
trap cleanup EXIT

export XDG_CONFIG_HOME="$TMP/config"
export XDG_DATA_HOME="$TMP/data"
export XDG_STATE_HOME="$TMP/state"
mkdir -p "$XDG_CONFIG_HOME/dev-journal"
PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
cat > "$XDG_CONFIG_HOME/dev-journal/config.yml" <<EOF
github:
  repositories: []
server:
  host: 127.0.0.1
  port: $PORT
  collection_enabled: false
EOF

cd "$ROOT"
uv run uvicorn server.main:app --host 127.0.0.1 --port "$PORT" >"$TMP/server.log" 2>&1 &
PID=$!
for _ in $(seq 1 50); do
  if curl --fail --silent "http://127.0.0.1:$PORT/api/health" | grep -q '"ok"'; then
    test -f "$XDG_DATA_HOME/dev-journal/journal.db"
    test ! -e "${HOME}/.local/share/dev-journal/journal.db.test-marker"
    exit 0
  fi
  sleep 0.1
done
cat "$TMP/server.log" >&2
exit 1
