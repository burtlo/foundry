"""P7: shape intake validation and blocked intake CLI surfacing."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from foundry_cli.engine.intake_executor import BLOCK_REASON_MISSING_WORK_PROMPT
from foundry_cli.user_cli import cmd_shape
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import shape_test_workspace

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"


def _run_cli(workspace: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--json",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            *argv,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_shape_rejects_empty_input_file(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    empty = tmp_path / "empty.md"
    empty.write_text("   \n", encoding="utf-8")
    result = _run_cli(workspace, "shape", "--input-file", str(empty), "--no-host")
    assert result.returncode != 0
    body = json.loads(result.stdout)
    assert body.get("ok") is False
    err = body.get("error") or {}
    assert err.get("code") == "INPUT_REQUIRED"
    assert "empty" in err.get("message", "").lower()


def test_shape_rejects_empty_inline_input(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    result = _run_cli(workspace, "shape", "--input", "   ", "--no-host")
    assert result.returncode != 0
    body = json.loads(result.stdout)
    assert body.get("error", {}).get("code") == "INPUT_REQUIRED"


def test_shape_accepts_prompt_alias(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    prompt = "Ship telemetry via --prompt alias"
    result = _run_cli(workspace, "shape", "--prompt", prompt, "--no-host")
    assert result.returncode == 0, result.stderr + result.stdout
    body = json.loads(result.stdout)
    assert body.get("ok") is True
    assert body.get("work_prompt") == prompt
    assert body.get("intake_status") == "passed"


def test_shape_surfaces_blocked_intake_as_cli_error(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    args = argparse.Namespace(
        workspace=workspace,
        registry=str(BUNDLE),
        input="Valid prompt text",
        input_file=None,
        flow=None,
        run_id=None,
        no_host=True,
        local=False,
        json=True,
    )
    blocked_advance = {
        "ok": True,
        "reason": "intake_blocked",
        "revision": 2,
        "detail": {
            "intake_status": "blocked",
            "block_reason": BLOCK_REASON_MISSING_WORK_PROMPT,
            "transitioned": False,
        },
    }
    with patch("foundry_cli.user_cli._advance_via_host_or_local", return_value=blocked_advance):
        result = cmd_shape(args)
    assert result.get("ok") is False
    err = result.get("error") or {}
    assert err.get("code") == "INTAKE_BLOCKED"
    assert result.get("block_reason") == BLOCK_REASON_MISSING_WORK_PROMPT
    assert result.get("intake_status") == "blocked"
    assert "blocked" in err.get("message", "").lower()
