import sqlite3
import stat
from pathlib import Path

from db import SCHEMA_SQL, SCHEMA_VERSION, get_connection, init_db

EXPECTED_TABLES = {
    "categories",
    "issues",
    "issue_states",
    "comments",
    "chat_threads",
    "chat_messages",
}


def test_schema_is_created_only_in_requested_temp_database(tmp_path: Path) -> None:
    db_path = tmp_path / "isolated" / "journal.db"
    init_db(str(db_path))
    assert db_path.exists()

    conn = get_connection(str(db_path))
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    conn.close()
    assert tables == EXPECTED_TABLES


def test_schema_keeps_issue_identity_contract() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(issues)")]
    assert columns == [
        "id",
        "issue_number",
        "repo",
        "title",
        "body",
        "labels_json",
        "url",
        "closed_at",
        "closed_date_jst",
        "category_id",
        "category_order",
        "deep_dive_json",
        "generated_at",
    ]


def test_migration_preserves_legacy_rows_and_sets_version(tmp_path: Path) -> None:
    db_path = tmp_path / "journal.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.execute(
        "INSERT INTO issues(issue_number,repo,title,url,closed_at,closed_date_jst) "
        "VALUES (1,'example/repo','kept','https://example.test/1','2024-01-01','2024-01-01')"
    )
    conn.commit()
    conn.close()

    init_db(str(db_path))
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT title FROM issues").fetchone()[0] == "kept"
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    conn.close()
    assert db_path.stat().st_mode & 0o777 == 0o600
    assert db_path.parent.stat().st_mode & 0o777 == 0o700


def test_in_memory_database_remains_supported() -> None:
    init_db(":memory:")


def test_newer_database_schema_is_rejected(tmp_path: Path) -> None:
    db_path = tmp_path / "journal.db"
    conn = sqlite3.connect(db_path)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.close()
    try:
        init_db(str(db_path))
    except RuntimeError as exc:
        assert "newer than supported" in str(exc)
    else:
        raise AssertionError("newer schema was accepted")


def test_explicit_database_preserves_existing_parent_permissions(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    init_db(str(shared / "journal.db"))
    assert stat.S_IMODE(shared.stat().st_mode) == 0o755
