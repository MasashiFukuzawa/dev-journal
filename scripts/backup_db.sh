#!/bin/bash
set -euo pipefail

DB_PATH="${XDG_DATA_HOME:-$HOME/.local/share}/dev-journal/journal.db"
BACKUP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/dev-journal/backups"
DATESTAMP=$(date +%Y%m%d_%H)
BACKUP_PATH="$BACKUP_DIR/journal_${DATESTAMP}.db"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
    echo "$(date): ERROR: DB not found at $DB_PATH" >&2
    exit 1
fi

sqlite3 "$DB_PATH" ".backup '$BACKUP_PATH'"
echo "$(date): Backed up to $BACKUP_PATH"

# 直近48時間分のみ保持（毎時バックアップ × 48 = 48ファイル）
find "$BACKUP_DIR" -name "journal_*.db" -mtime +2 -delete
echo "$(date): Pruned backups older than 48 hours"
