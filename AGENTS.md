# Repository instructions

- Preserve the existing CLI commands, API routes, SQLite schema, launchd labels, and clone-based runtime path unless a migration is explicitly approved.
- Keep public documentation in English. Keep the agent skill's user-facing instructions primarily in Japanese.
- Never commit configuration, databases, logs, issue content, credentials, email addresses, private paths, or organization-specific identifiers.
- Run tests with temporary `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, and `XDG_STATE_HOME`; never inspect or mutate a user's production journal database.
- Maintain loopback and trusted-host defaults. Any wider bind must be an explicit, documented opt-in.
- Run the checks in [Delegated scope](#delegated-scope) on the final revision before reporting a change complete.

## Delegated scope

What a session may decide and do without asking. It applies to every session in this repository, and the `autopilot` skill of the `toolbox` plugin reads it for a goal. It widens nothing in the instructions above, [CONTRIBUTING.md](CONTRIBUTING.md), or [SECURITY.md](SECURITY.md): where they differ, those rules win.

### May do without asking

- On a feature branch: edit code, tests, and documentation, run the checks, and open pull requests.
- Choose implementation details where the choice can be undone.
- Remove worktrees, branches, containers, and temporary files created for the current goal, except anything with uncommitted or unpushed work or with data.

### Must ask

- Breaking the existing CLI commands, API routes, SQLite schema, launchd labels, or clone-based runtime path: a migration needs explicit approval, as in the instructions above, and a change to persisted data or a compatibility contract starts with an issue ([CONTRIBUTING.md](CONTRIBUTING.md)).
- Production operations: installing, changing, or removing the launchd services, and anything else that touches a user's installed runtime or configuration. The production journal database stays off limits, as in the instructions above.
- Deleting data, and any operation that cannot be undone.
- Publishing or sending anything outside this repository.
- Anything that adds cost.
- Facts only a person knows.

### Checks and merge

- Checks: `uv run ruff check .`, `uv run pytest`, and `tests/smoke_server.sh`, on the final revision. This also holds for a one-off change and for a change that is already committed on the branch. When `web/` changes, also run `cd web && npm run lint && npm run build`.
- Changes that need a deeper look are not complete until a second model has reviewed them (`second-opinion`; the session chooses the provider):
  - any change to `server/main.py`, `server/deps.py`, `cli/db.py`, or `cli/collect.py`
  - wherever they occur: changes to the default bind, Host, or authentication boundary of the server; SQLite schema changes; changes to the GitHub Project collection scope (`project_owner`, `project_number`, `repositories`); and changes to the private-data exclusion logic (the criteria in `tests/scan_public_content.sh` and `tests/test_no_private_data.py`)
- Changes only to `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, or `LICENSE` need the checks only.
- Always review: that no private identifier, credential, or issue body is committed, including leak paths that the patterns in `tests/scan_public_content.sh` do not catch; that the default bind, Host, and authentication boundary of the server (loopback, `allowed_hosts`) is not loosened; that backward compatibility of the SQLite schema, CLI commands, and API routes is not broken without approval; and that a change to the GitHub Project collection scope does not widen what is collected by accident.
- Merge: a human approves merges.
