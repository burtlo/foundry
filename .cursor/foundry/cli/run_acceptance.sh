#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${ROOT}/.venv/bin/python"
REPO_ROOT="$(cd "${ROOT}/../../.." && pwd)"
if [[ -x "${VENV_PYTHON}" ]]; then
  exec "${VENV_PYTHON}" "${ROOT}/foundry.py" --workspace "${REPO_ROOT}" dev acceptance "$@"
fi
exec python3 "${ROOT}/foundry.py" --workspace "${REPO_ROOT}" dev acceptance "$@"
