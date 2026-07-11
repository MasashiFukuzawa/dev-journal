# dev-journal

`dev-journal` turns completed GitHub issues into a searchable development journal. It stores issue metadata in SQLite, uses Claude CLI for structured analysis, and serves a local FastAPI + React interface.

## Setup

Requirements: Python 3.12+, `uv`, `gh`, Claude CLI, and Node.js for rebuilding the UI.

```bash
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/dev-journal"
cp config.example.yml "${XDG_CONFIG_HOME:-$HOME/.config}/dev-journal/config.yml"
uv sync
cd web && npm ci && npm run build
```

Edit `github.repositories` in the copied configuration, then start the server:

```bash
./scripts/run_server.sh
```

The server listens on `127.0.0.1:8421` by default. The analysis runtime intentionally uses Claude CLI; the agent skill itself is compatible with Claude Code and Codex.

Configuration precedence is `--config`, then `DEV_JOURNAL_CONFIG`, then the XDG configuration path. Runtime data and state use XDG directories and are never stored in the repository.

## macOS service

`launchd/install.sh` renders machine-local plists into `~/Library/LaunchAgents`. No user-specific path is committed to the repository.

## Security

Issue bodies and comments may contain confidential data. Keep the database local, review repository access, and do not expose the web server beyond loopback without adding authentication and a trusted network boundary.

## License

Apache License 2.0. See [LICENSE](LICENSE).
