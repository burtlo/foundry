#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${ROOT}/.venv/bin/python"
if [[ -x "${VENV_PYTHON}" ]]; then
  exec "${VENV_PYTHON}" "${ROOT}/foundry.py" "$@"
fi
exec python3 "${ROOT}/foundry.py" "$@"
