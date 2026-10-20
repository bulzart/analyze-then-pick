#!/usr/bin/env bash
# macOS / Linux / Git Bash wrapper: finds Python 3.10+ and runs install.py with the same arguments.
# Usage:  bash install.sh [--force] [--no-deps] [--no-mcp] [--dry-run]
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1; then
    exec "$(command -v "$c")" "$here/install.py" "$@"
  fi
done
echo "Python 3.10+ not found. Install it, then run this again." >&2
exit 1
