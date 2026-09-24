#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FOUNDRY_SCRIPT="${SCRIPT_DIR}/foundry.py"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$FOUNDRY_SCRIPT" "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python "$FOUNDRY_SCRIPT" "$@"
fi

echo "python or python3 was not found on PATH" >&2
exit 1
