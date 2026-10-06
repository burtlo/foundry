"""Workflow-02 slices 2C–2F: commit through deliver.stub."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.execute_step_executor import _git_run, _snapshot_state
from foundry_cli.engine.gates import resolve_engine_gate_decision
from foundry_cli.registry import load_registry
from foundry_cli.run_service import execute_start_durable, get_run
from foundry_cli.run_store import load_snapshot, save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.git_workspace import ensure_clean_git_workspace

BUNDLE = FOUNDRY_ROOT
FIXTURE_RECORD_GATE = "porcelain-0007-v007-record-gate"
CLI = BUNDLE / "cli" / "foundry.py"


def _workspace_with_fixture(tmp_path: Path, fixture_name: str) -> tuple[Path, str]:
    src = BUNDLE / "fixtures" / "runs" / fixture_name
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
    ensure_clean_git_workspace(workspace)
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


def _authorize_execute(workspace: Path, run_id: str) -> None:
    decide = _run_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
    assert decide.returncode == 0, decide.stderr + decide.stdout
    advance = _run_cli(workspace, "run", "advance", "--run", run_id)
    assert advance.returncode == 0, advance.stderr + advance.stdout
    ensure_clean_git_workspace(workspace)
    start = execute_start_durable(workspace=workspace, bundle=BUNDLE, run_id=run_id)
    assert start.get("ok") is True, start


def _enable_review(workspace: Path, run_id: str) -> None:
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    config = snapshot.setdefault("config", {})
    if isinstance(config, dict):
        config["review"] = {"enabled": True}
        config.setdefault("limits", {"repair": 2, "reverify": 2})
    save_snapshot(run_dir, snapshot)


def _ensure_feature_branch_diff(workspace: Path, snapshot: dict) -> None:
    """Stub execute commit uses --allow-empty; verify intake requires a non-empty branch diff."""
    state = _snapshot_state(snapshot)
    feature = state.get("feature_branch")
    default = state.get("default_branch") or "main"
    if not isinstance(feature, str) or not feature.strip():
        return
    diff = _git_run(workspace, "diff", f"{default}...{feature}")
    if diff.returncode in (0, 1) and (diff.stdout or "").strip():
        return
    checkout = _git_run(workspace, "checkout", feature)
    if checkout.returncode != 0:
        return
    marker = workspace / ".foundry" / "execute-stub-diff.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"stub diff for {snapshot.get('run_id')}\n", encoding="utf-8")
    _git_run(workspace, "add", ".foundry/execute-stub-diff.txt")
    _git_run(workspace, "commit", "-m", "foundry: stub execute diff for verify")
    ensure_clean_git_workspace(workspace)


def _advance_to_execute_commit(workspace: Path, run_id: str) -> dict:
    """Advance through execute intake..test gates to opened execute.commit."""
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    for _ in range(48):
        active = snapshot.get("active_visit") or {}
        if active.get("node_id") == "execute.commit" and active.get("lifecycle") == "opened":
            break
        outcome = advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
            step_budget=1,
        )
        if not outcome.get("steps_taken"):
            reason = str(outcome.get("reason") or "")
            if reason in ("execute_build_boundary", "repair_reentry_boundary"):
                continue
            break
    save_snapshot(run_dir, snapshot)
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") == "execute.commit", active.get("node_id")
    _ensure_feature_branch_diff(workspace, snapshot)
    return snapshot


@pytest.fixture(autouse=True)
def _stub_execute_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    monkeypatch.setenv("FOUNDRY_VERIFY_ACCEPTANCE_DECISION", "pass")
    monkeypatch.delenv("FOUNDRY_EXECUTE_TEST_EXIT_CODE", raising=False)
    monkeypatch.delenv("FOUNDRY_EXECUTE_COMMIT_EXIT_CODE", raising=False)
    monkeypatch.delenv("FOUNDRY_EXECUTE_CODE_QUALITY_EXIT_CODE", raising=False)


def test_execute_commit_gate_passes_with_final_sha(tmp_path: Path) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _authorize_execute(workspace, run_id)
    snapshot = _advance_to_execute_commit(workspace, run_id)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    for _ in range(24):
        active = snapshot.get("active_visit") or {}
        if active.get("node_id") == "execute.commit.gate":
            break
        advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
            step_budget=1,
        )
    save_snapshot(run_dir, snapshot)
    state = snapshot.get("state") or {}
    assert state.get("final_commit_sha")
    visit = snapshot.get("active_visit") or {}
    assert visit.get("node_id") == "execute.commit.gate"
    gate = resolve_engine_gate_decision(
        snapshot,
        {"id": visit["id"], "node_id": "execute.commit.gate", "kind": "gate"},
        flow,
        run_dir=run_dir,
    )
    assert gate.get("ok") is True
    assert gate.get("decision") == "pass"


def test_verify_intake_gate_passes_with_intake_receipt(tmp_path: Path) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _authorize_execute(workspace, run_id)
    snapshot = _advance_to_execute_commit(workspace, run_id)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    for _ in range(6):
        advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
            step_budget=1,
        )
    intake_gate = next(
        (v for v in snapshot.get("visits", []) if v.get("node_id") == "verify.intake.gate"),
        None,
    )
    assert intake_gate is not None
    gate = resolve_engine_gate_decision(
        snapshot,
        {"id": intake_gate["id"], "node_id": "verify.intake.gate", "kind": "gate"},
        flow,
        run_dir=run_dir,
    )
    assert gate.get("decision") == "pass"


def test_verify_acceptance_gate_reads_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_VERIFY_ACCEPTANCE_DECISION", "replan")
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _authorize_execute(workspace, run_id)
    _enable_review(workspace, run_id)
    snapshot = _advance_to_execute_commit(workspace, run_id)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    for _ in range(80):
        advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
            step_budget=1,
        )
        active = snapshot.get("active_visit") or {}
        if active.get("node_id") == "execute.plan":
            break
    acceptance_gate = next(
        (v for v in snapshot.get("visits", []) if v.get("node_id") == "verify.acceptance.gate"),
        None,
    )
    assert acceptance_gate is not None
    assert acceptance_gate.get("decision") == "replan"


def test_full_path_reaches_deliver_stub_with_handoff(tmp_path: Path) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _authorize_execute(workspace, run_id)
    _enable_review(workspace, run_id)
    snapshot = _advance_to_execute_commit(workspace, run_id)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id

    for _ in range(120):
        active = snapshot.get("active_visit") or {}
        node_id = str(active.get("node_id") or "")
        kind = str(active.get("kind") or "")
        if snapshot.get("status") == "completed":
            break
        if kind == "gate" and active.get("decision") is None and node_id in (
            "verify.code_review.gate",
            "verify.complete.gate",
        ):
            save_snapshot(run_dir, snapshot)
            decide = _run_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
            assert decide.returncode == 0, decide.stderr + decide.stdout
            advance = _run_cli(workspace, "run", "advance", "--run", run_id)
            assert advance.returncode == 0, advance.stderr + advance.stdout
            snapshot = load_snapshot(run_dir)
            if snapshot.get("status") == "completed":
                break
            continue
        outcome = advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
            step_budget=1,
        )
        if not outcome.get("steps_taken"):
            reason = str(outcome.get("reason") or "")
            if reason in ("execute_build_boundary", "repair_reentry_boundary"):
                continue
            if reason == "wait" and kind == "gate":
                continue
            break
        if snapshot.get("status") == "completed":
            break
        save_snapshot(run_dir, snapshot)
    save_snapshot(run_dir, snapshot)

    assert snapshot.get("status") == "completed"
    state = snapshot.get("state") or {}
    assert isinstance(state.get("deliver_handoff_message"), str)
    assert "ready to hand off" in state["deliver_handoff_message"].lower()

    status = get_run(workspace, run_id=run_id)
    assert status.get("ok") is True
    assert status.get("handoff_message")
