import sqlite3
from pathlib import Path

from db import SCHEMA_SQL, get_connection, init_db

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
