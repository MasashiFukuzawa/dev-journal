#!/bin/bash
set -euo pipefail

patterns='(/Users/|works/private|[[:alnum:]._%+-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}|(api[_-]?key|client[_-]?secret|access[_-]?token)[[:space:]]*[:=][[:space:]]*[^[:space:]]{8,})'
if [ "${1:-}" = "--stdin" ]; then
  if rg -n -i "$patterns" -; then
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
  rg -n -i "$patterns" . \
    --glob '!.git/**' --glob '!.venv/**' --glob '!web/node_modules/**' \
    --glob '!tests/scan_public_content.sh' --glob '!tests/test_no_private_data.py' || {
    status=$?
    [ "$status" -eq 1 ] && exit 0
    exit "$status"
  }
fi

echo "Potential private identifier or secret found" >&2
exit 1
