# Repository instructions

- Preserve the existing CLI commands, API routes, SQLite schema, launchd labels, and clone-based runtime path unless a migration is explicitly approved.
- Keep public documentation in English. Keep the agent skill's user-facing instructions primarily in Japanese.
- Never commit configuration, databases, logs, issue content, credentials, email addresses, private paths, or organization-specific identifiers.
- Run tests with temporary `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, and `XDG_STATE_HOME`; never inspect or mutate a user's production journal database.
- Maintain loopback and trusted-host defaults. Any wider bind must be an explicit, documented opt-in.
- Run the commands in `.agents/done.yml` before reporting a change complete.
