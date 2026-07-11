#!/bin/bash
# dev-journal の launchd ジョブを登録する（plist は repo 内が正・LaunchAgents へ symlink）
# データは ~/.local/share/dev-journal/（repo 内には置かない）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/dev-journal"

mkdir -p "${XDG_DATA_HOME:-$HOME/.local/share}/dev-journal"
mkdir -p "$LAUNCH_DIR"
mkdir -p "$STATE_DIR"

for plist in com.dev-journal.server.plist com.dev-journal.backup.plist; do
    target="$LAUNCH_DIR/$plist"
    launchctl bootout "gui/$(id -u)/${plist%.plist}" 2>/dev/null || true
    sed -e "s|__REPO_ROOT__|$REPO_ROOT|g" -e "s|__STATE_DIR__|$STATE_DIR|g" \
        "$SCRIPT_DIR/$plist.template" > "$target"
    launchctl bootstrap "gui/$(id -u)" "$target"
    echo "Loaded $plist"
done

echo ""
echo "Done."
echo "  Server:  http://localhost:8421 (KeepAlive, auto-starts now)"
echo "  Backup:  hourly → ${XDG_DATA_HOME:-$HOME/.local/share}/dev-journal/backups/ (48h保持)"
echo "  Status:  launchctl list | grep dev-journal"
