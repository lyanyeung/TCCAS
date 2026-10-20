#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
MODE="${1:-copy}"
if [[ "$MODE" != copy && "$MODE" != move ]]; then
  echo "Usage: bash scripts/run_once.sh [copy|move]" >&2; exit 2
fi
echo "=== Inventory ==="
python3 scripts/archive_tccas.py inspect
echo "=== Transfer mode: $MODE ==="
python3 scripts/archive_tccas.py "$MODE"
echo "=== Quota after transfer ==="
if command -v myfiles >/dev/null 2>&1; then myfiles; fi
