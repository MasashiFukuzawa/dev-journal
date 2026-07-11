#!/usr/bin/env python3
"""Delete issues older than 90 days (by closed_date_jst)."""

import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from config import load_config
from db import get_connection, init_db


def main() -> None:
    init_db()
    conn = get_connection()
    cfg = load_config()
    cutoff = (
        datetime.now(ZoneInfo(cfg.timezone)).date() - timedelta(days=cfg.retention_days)
    ).isoformat()
    with conn:
        result = conn.execute("DELETE FROM issues WHERE closed_date_jst < ?", (cutoff,))
    print(f"Pruned {result.rowcount} issue(s) older than {cutoff}.", file=sys.stderr)
    conn.close()


if __name__ == "__main__":
    main()
