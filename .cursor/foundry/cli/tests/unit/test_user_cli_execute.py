"""Unit tests for user-facing execute/supervision CLI (start, cancel, retry)."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.ledger import ledger_events
from foundry_cli.run_store import load_snapshot
from tests.unit.constants import FIXTURE_PORCELAIN_RECORD_GATE
from tests.unit.git_workspace import ensure_clean_git_workspace
from tests.unit.implementation_flow_helpers import invoke_foundry_cli, workspace_with_run_fixture


def _park_at_execute_start(workspace: Path, run_id: str) -> None:
    decide = invoke_foundry_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
    assert decide.returncode == 0, decide.stderr + decide.stdout
    advance = invoke_foundry_cli(workspace, "run", "advance", "--run", run_id)
    assert advance.returncode == 0, advance.stderr + advance.stdout
    body = json.loads(advance.stdout)
    assert body.get("active_node_id") == "execute.start"
    assert body.get("wait", {}).get("kind") == "decision"
    ensure_clean_git_workspace(workspace)


def test_start_authorizes_and_advances_to_execute_intake(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    _park_at_execute_start(workspace, run_id)
    ensure_clean_git_workspace(workspace)

    start = invoke_foundry_cli(workspace, "start", run_id, "--no-host")
    assert start.returncode == 0, start.stderr + start.stdout
    body = json.loads(start.stdout)
    assert body.get("ok") is True
    assert body.get("authorization_recorded") is True
    assert body.get("active_node_id") == "execute.build"
    assert body.get("phase") == "execute"
    wait = body.get("wait") or {}
    assert wait.get("kind") in (None, "operator")

    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    types = [e.get("type") for e in ledger_events(snapshot) if isinstance(e, dict)]
    assert "execute.authorization.recorded" in types


def test_start_rejects_wrong_node(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    start = invoke_foundry_cli(workspace, "start", run_id, "--no-host")
    assert start.returncode != 0
    body = json.loads(start.stdout)
    assert body.get("error", {}).get("code") == "EXECUTE_START_GATE_REQUIRED"


def test_cancel_requires_reason(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    cancel = invoke_foundry_cli(workspace, "cancel", run_id)
    assert cancel.returncode != 0
    if cancel.stdout.strip():
        body = json.loads(cancel.stdout)
        assert body.get("error", {}).get("code") in {"REASON_REQUIRED", "INVALID_FLAGS"}
    else:
        assert "reason" in cancel.stderr.lower()


def test_cancel_halts_run_with_reason(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    _park_at_execute_start(workspace, run_id)
    cancel = invoke_foundry_cli(
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
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    _park_at_execute_start(workspace, run_id)
    cancel = invoke_foundry_cli(
        workspace,
        "cancel",
        run_id,
        "--reason",
        "pause",
    )
    assert cancel.returncode == 0

    retry = invoke_foundry_cli(workspace, "retry", run_id, "--reason", "resume work")
    assert retry.returncode == 0, retry.stderr + retry.stdout
    body = json.loads(retry.stdout)
    assert body.get("status") == "running"
    assert body.get("active_node_id") == "execute.start"
