import sqlite3
from pathlib import Path

from config import data_dir, ensure_private_dir, ensure_private_file

SCHEMA_VERSION = 4


def default_db_path() -> Path:
    return data_dir() / "journal.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_number  INTEGER NOT NULL,
    repo          TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT,
    labels_json   TEXT NOT NULL DEFAULT '[]',
    url           TEXT NOT NULL,
    closed_at     TEXT NOT NULL,
    closed_date_jst TEXT NOT NULL,
    category_id      INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    category_order   INTEGER,
    deep_dive_json TEXT,
    generated_at  TEXT,
    UNIQUE(repo, issue_number)
);

CREATE INDEX IF NOT EXISTS idx_issues_closed_date ON issues(closed_date_jst);
CREATE INDEX IF NOT EXISTS idx_issues_category
ON issues(closed_date_jst, category_order, closed_at);

CREATE TABLE IF NOT EXISTS issue_states (
    repo          TEXT NOT NULL,
    issue_number  INTEGER NOT NULL,
    is_confirmed INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY(repo, issue_number),
    FOREIGN KEY(repo, issue_number) REFERENCES issues(repo, issue_number) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_pk    INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    author      TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_threads (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    title           TEXT,
    issue_refs_json TEXT NOT NULL DEFAULT '[]',
    last_read_assistant_message_id INTEGER,
    last_read_at    TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   TEXT NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'done',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_thread ON chat_messages(thread_id, id);
CREATE INDEX IF NOT EXISTS idx_issue_states_confirmed ON issue_states(is_confirmed);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    if db_path == ":memory:":
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    path = Path(db_path) if db_path else default_db_path()
    if path.parent != Path("."):
        if db_path:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        else:
            ensure_private_dir(path.parent)
    ensure_private_file(path, create=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    ensure_private_file(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: str | None = None) -> None:
    """Create tables if they don't exist. Idempotent."""
    conn = get_connection(db_path)
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if current_version > SCHEMA_VERSION:
        conn.close()
        raise RuntimeError(
            f"database schema version {current_version} is newer than supported {SCHEMA_VERSION}"
        )
    conn.executescript(SCHEMA_SQL)
    def add_column_if_missing(table: str, column: str, declaration: str) -> None:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    add_column_if_missing("chat_messages", "status", "TEXT NOT NULL DEFAULT 'done'")
    add_column_if_missing(
        "chat_threads", "last_read_assistant_message_id", "INTEGER"
    )
    add_column_if_missing("chat_threads", "last_read_at", "TEXT")
    conn.commit()

    conn.execute("""
        UPDATE chat_threads
        SET
            last_read_assistant_message_id = (
                SELECT MAX(cm.id)
                FROM chat_messages cm
                WHERE cm.thread_id = chat_threads.id
                  AND cm.role = 'assistant'
                  AND cm.status = 'done'
            ),
            last_read_at = COALESCE(last_read_at, datetime('now'))
        WHERE last_read_assistant_message_id IS NULL
          AND EXISTS (
              SELECT 1
              FROM chat_messages cm
              WHERE cm.thread_id = chat_threads.id
                AND cm.role = 'assistant'
                AND cm.status = 'done'
          )
    """)
    conn.commit()

    # Migration: remove duplicate chat_threads per issue_refs_json, keeping the thread
    # with the most messages (tie-break: earliest created_at). Must run before UNIQUE INDEX.
    conn.executescript("""
        DELETE FROM chat_threads WHERE id IN (
            SELECT id FROM (
                WITH ranked AS (
                    SELECT
                        ct.id,
                        ct.issue_refs_json,
                        ct.created_at,
                        COUNT(cm.id) AS msg_count,
                        ROW_NUMBER() OVER (
                            PARTITION BY ct.issue_refs_json
                            ORDER BY COUNT(cm.id) DESC, ct.created_at ASC
                        ) AS rn
                    FROM chat_threads ct
                    LEFT JOIN chat_messages cm ON cm.thread_id = ct.id
                    GROUP BY ct.id, ct.issue_refs_json, ct.created_at
                )
                SELECT id FROM ranked WHERE rn > 1
            )
        );
    """)

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_threads_issue_refs "
        "ON chat_threads(issue_refs_json)"
    )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()

    conn.close()
