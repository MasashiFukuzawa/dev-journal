# dev-journal

`dev-journal` turns completed GitHub issues into a searchable development journal. It stores issue metadata in a local SQLite database, uses Claude CLI in tool-free mode for structured analysis, and serves a local FastAPI and React interface.

The bundled agent skill works with Claude Code and Codex. The analysis subprocess intentionally remains Claude CLI based.

## Requirements

- macOS or Linux with Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- GitHub CLI (`gh`) authenticated for the configured repositories and Project
- Claude CLI authenticated for analysis
- Node.js 24+ only when rebuilding the web interface
- `sqlite3` for backups

## Install from a clone

```bash
git clone https://github.com/MasashiFukuzawa/dev-journal.git
cd dev-journal
uv sync
(cd web && npm ci && npm run build)
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/dev-journal"
cp config.example.yml "${XDG_CONFIG_HOME:-$HOME/.config}/dev-journal/config.yml"
```

Add the checkout's `bin` directory to `PATH`, or invoke `./bin/dev-journal`. If an automation does not run from the checkout, set `DEV_JOURNAL_HOME` to its absolute path. Existing direct script invocations remain supported.

```bash
dev-journal serve
dev-journal collect fetch-pending
dev-journal prune
```

Configuration precedence is `--config`, then `DEV_JOURNAL_CONFIG`, then `${XDG_CONFIG_HOME:-$HOME/.config}/dev-journal/config.yml`. Runtime data and state use XDG directories and are never stored in the checkout.

## Configure GitHub collection

Set `github.project_owner` and `github.project_number` to scope collection to exactly one GitHub Project. `github.repositories` optionally restricts the Project items to an allowlist. Project pagination is automatic.

Older configurations without a Project scope continue to work and emit a warning. This legacy mode matches `done_status` in any Project attached to a closed issue and can therefore collect an unrelated item; migrate it before team use.

The legacy database column `closed_date_jst` is preserved for compatibility. Despite its historical name, new values use the configured `timezone`.

## Web server security

The default server binds to `127.0.0.1:8421`, accepts only configured trusted Host headers, and serves SPA routes as `index.html` rather than arbitrary files. Issue bodies, comments, and chat messages can be confidential.

Binding beyond loopback requires both `server.allow_unsafe_non_loopback: true` and an explicit `server.allowed_hosts` allowlist. The application does not provide authentication, so place it behind an authenticated trusted boundary.

Raw Claude output is not persisted by default. `analysis.save_raw_output: true` is intended only for short-lived debugging and stores the output with owner-only permissions.

The default `claude-sonnet-4-6` model is retained for configuration compatibility. New installations may select an available Sonnet 5 model in `analysis.model`; verify the exact model ID with the installed Claude CLI rather than assuming a moving alias.

## Agent plugin

Claude Code can add this repository as a marketplace and install `dev-journal`. Codex can install it from the repository's Codex marketplace metadata. The plugin supplies the skill only; clone the runtime separately as described above.

## macOS service

```bash
dev-journal install-service
dev-journal service-status
dev-journal uninstall-service
```

The installer renders machine-local plists into `~/Library/LaunchAgents`. The server and backup labels remain `com.dev-journal.server` and `com.dev-journal.backup`. Backups retain the newest 48 hourly snapshots.

## Update and uninstall

Update with `git pull`, then run `uv sync` and rebuild the web interface. Before deleting a checkout, run `dev-journal uninstall-service`. Configuration, database, and state remain in their XDG locations until explicitly removed.

## Development

```bash
uv run ruff check .
uv run pytest
tests/smoke_server.sh
(cd web && npm ci && npm run lint && npm run build)
```

Tests must point all XDG variables at temporary directories and must never open a production database.

## License

Apache License 2.0. See [LICENSE](LICENSE).
