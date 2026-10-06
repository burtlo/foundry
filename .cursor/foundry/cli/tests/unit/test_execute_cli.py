"""Unit tests for Phase 6 execute / verify user CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from foundry_cli.ledger import ledger_events
from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.git_workspace import ensure_clean_git_workspace
FIXTURE_RECORD_GATE = "porcelain-0007-v007-record-gate"

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"
FIXTURES = BUNDLE / "fixtures" / "runs"


def _workspace_with_fixture(tmp_path: Path, fixture_name: str) -> tuple[Path, str]:
    src = FIXTURES / fixture_name
    snapshot = json.loads((src / "snapshot.json").read_text(encoding="utf-8"))
    run_id = str(snapshot.get("run_id") or fixture_name)
    workspace = tmp_path / "app"
    dest = workspace / ".foundry" / "runs" / run_id
    shutil.copytree(src, dest)
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
        dirs_exist_ok=True,
    )
    return workspace, run_id


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


def _park_at_execute_start(workspace: Path, run_id: str) -> None:
    decide = _run_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
    assert decide.returncode == 0, decide.stderr + decide.stdout
    advance = _run_cli(workspace, "run", "advance", "--run", run_id)
    assert advance.returncode == 0, advance.stderr + advance.stdout
    body = json.loads(advance.stdout)
    assert body.get("active_node_id") == "execute.start"
    assert body.get("wait", {}).get("kind") == "decision"
    ensure_clean_git_workspace(workspace)


def test_start_authorizes_and_advances_to_execute_intake(tmp_path: Path) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _park_at_execute_start(workspace, run_id)

    start = _run_cli(workspace, "start", run_id, "--no-host")
    assert start.returncode == 0, start.stderr + start.stdout
    body = json.loads(start.stdout)
    assert body.get("ok") is True
    assert body.get("authorization_recorded") is True
    assert body.get("active_node_id") == "execute.intake"
    assert body.get("phase") == "execute"
    wait = body.get("wait", {})
    assert wait.get("kind") == "operator"
    assert wait.get("request_ref") == "unsupported:execute.intake"
    assert "not yet implemented" in str(wait.get("summary") or "").lower()

    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    types = [e.get("type") for e in ledger_events(snapshot) if isinstance(e, dict)]
    assert "execute.authorization.recorded" in types


def test_start_rejects_wrong_node(tmp_path: Path) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    start = _run_cli(workspace, "start", run_id, "--no-host")
    assert start.returncode != 0
    body = json.loads(start.stdout)
    assert body.get("error", {}).get("code") == "EXECUTE_START_GATE_REQUIRED"


def test_cancel_requires_reason(tmp_path: Path) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    cancel = _run_cli(workspace, "cancel", run_id)
    assert cancel.returncode != 0
    if cancel.stdout.strip():
        body = json.loads(cancel.stdout)
        assert body.get("error", {}).get("code") in {"REASON_REQUIRED", "INVALID_FLAGS"}
    else:
        assert "reason" in cancel.stderr.lower()


def test_cancel_halts_run_with_reason(tmp_path: Path) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _park_at_execute_start(workspace, run_id)
    cancel = _run_cli(
        workspace,
        "cancel",
        run_id,
        "--reason",
        "stopping for lunch",
    )
    assert cancel.returncode == 0, cancel.stderr + cancel.stdout
    body = json.loads(cancel.stdout)
    assert body.get("status") == "halted"
    assert body.get("reason") == "stopping for lunch"


def test_retry_after_cancel(tmp_path: Path) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _park_at_execute_start(workspace, run_id)
    cancel = _run_cli(
        workspace,
        "cancel",
        run_id,
        "--reason",
        "pause",
    )
    assert cancel.returncode == 0

    retry = _run_cli(workspace, "retry", run_id, "--reason", "resume work")
    assert retry.returncode == 0, retry.stderr + retry.stdout
    body = json.loads(retry.stdout)
    assert body.get("status") == "running"
    assert body.get("active_node_id") == "execute.start"
