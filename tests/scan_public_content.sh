#!/bin/bash
set -euo pipefail

patterns='(/Users/|works/private|[[:alnum:]._%+-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}|(api[_-]?key|client[_-]?secret|access[_-]?token)[[:space:]]*[:=][[:space:]]*[^[:space:]]{8,})'

if [ "${1:-}" = "--stdin" ]; then
  # Input is `git log -p` output, which mixes commit metadata with diff
  # payload. Two things have to be handled before matching:
  #   - Author/trailer lines carry addresses that are already public in every
  #     commit and cannot be removed without rewriting history.
  #   - A leading `+`/`-` diff marker is otherwise consumed as an email local
  #     part, so `+@AGENTS.md` and `+@router.get(...)` look like addresses.
  # Scanning only added and removed content, with the marker stripped, covers
  # every line that ever entered a file and drops both classes of noise.
  # NR is kept so a hit still points at a line in the original stream.
  if awk '/^[-+]/ { printf "%d:%s\n", NR, substr($0, 2) }' | grep -EI -i "$patterns"; then
    echo "Potential private identifier or secret found in history" >&2
    exit 1
  fi
  exit 0
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git ls-files --error-unmatch README.md >/dev/null 2>&1; then
  git grep -nEI "$patterns" -- . \
    ':!tests/scan_public_content.sh' ':!tests/test_no_private_data.py' || {
    status=$?
    [ "$status" -eq 1 ] && exit 0
    exit "$status"
  }
else
  grep -rnEI -i "$patterns" . \
    --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
    --exclude=scan_public_content.sh --exclude=test_no_private_data.py || {
    status=$?
    [ "$status" -eq 1 ] && exit 0
    exit "$status"
  }
fi

echo "Potential private identifier or secret found" >&2
exit 1
