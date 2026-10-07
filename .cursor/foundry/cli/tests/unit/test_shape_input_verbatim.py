"""Verbatim shape request persistence (F9)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from foundry_cli.engine.run_config import work_prompt_from_snapshot
from foundry_cli.run_service import create_run
from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import shape_test_workspace

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"


def test_create_run_stores_verbatim_work_prompt_with_whitespace(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    prompt = "  leading and trailing spaces  \n"
    outcome = create_run(workspace=workspace, bundle=BUNDLE, work_prompt=prompt)
    assert outcome.get("ok") is True
    run_id = outcome["run_id"]
    snapshot = load_snapshot(workspace / ".foundry" / "runs" / run_id)
    assert work_prompt_from_snapshot(snapshot) == prompt
    shape_cfg = snapshot["config"]["shape"]
    assert shape_cfg["work_prompt"] == prompt


def test_user_cli_shape_preserves_verbatim_input(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    prompt = "\n  verbatim boundary\n"
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--json",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            "shape",
            "--input",
            prompt,
            "--no-host",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    body = json.loads(result.stdout)
    assert body.get("work_prompt") == prompt
    run_id = body["run_id"]
    snapshot = load_snapshot(workspace / ".foundry" / "runs" / run_id)
    ticket = snapshot.get("state", {}).get("ticket")
    assert isinstance(ticket, dict)
    assert ticket.get("raw_input") == prompt
