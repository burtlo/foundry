"""Unit tests for foundry.py CLI entrypoint."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[2]
CLI_ENTRY = CLI_DIR / "foundry.py"
REPO_ROOT = CLI_DIR.parents[2]
FIXTURE_RUN_DIR = REPO_ROOT / ".cursor" / "foundry" / "fixtures" / "runs" / "porcelain-0007-v001"


def test_run_context_rejects_json_and_markdown_together() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI_ENTRY),
            "--workspace",
            str(REPO_ROOT),
            "--registry",
            str(REPO_ROOT / ".cursor" / "foundry"),
            "--json",
            "run",
            "context",
            "--run-dir",
            str(FIXTURE_RUN_DIR),
            "--markdown",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1, completed.stdout or completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_FLAGS"
