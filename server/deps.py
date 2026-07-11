import sqlite3
import sys
from pathlib import Path

_cli_dir = str(Path(__file__).parent.parent / "cli")
if _cli_dir not in sys.path:
    sys.path.insert(0, _cli_dir)

from db import default_db_path  # noqa: E402


def get_db():
    """FastAPI dependency that yields a DB connection per request."""
    conn = sqlite3.connect(str(default_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()
