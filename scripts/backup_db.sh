#!/bin/bash
set -euo pipefail

DB_PATH="${XDG_DATA_HOME:-$HOME/.local/share}/dev-journal/journal.db"
BACKUP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/dev-journal/backups"
DATESTAMP=$(date +%Y%m%d_%H)
BACKUP_PATH="$BACKUP_DIR/journal_${DATESTAMP}.db"

mkdir -p -m 700 "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
    echo "$(date): ERROR: DB not found at $DB_PATH" >&2
    exit 1
fi

sqlite3 "$DB_PATH" ".backup '$BACKUP_PATH'"
chmod 600 "$BACKUP_PATH"
echo "$(date): Backed up to $BACKUP_PATH"

# Keep exactly the newest 48 hourly snapshots, independent of clock changes.
python3 "$(cd "$(dirname "$0")" && pwd -P)/prune_backups.py" "$BACKUP_DIR" --keep 48
echo "$(date): Retained the newest 48 backups"
