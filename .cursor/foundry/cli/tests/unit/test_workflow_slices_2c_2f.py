"""Workflow-02 slices 2C–2F: commit through deliver.stub."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.gates import resolve_engine_gate_decision
from foundry_cli.registry import load_registry
from foundry_cli.run_service import get_run
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import FIXTURE_PORCELAIN_RECORD_GATE
from tests.unit.implementation_flow_helpers import (
    advance_snapshot_to_execute_commit,
    advance_stub_run_to_completion,
    authorize_execute_start,
    enable_verify_review,
    workspace_with_run_fixture,
)
from tests.unit.snapshot_helpers import resolve_gate_at_node

BUNDLE = FOUNDRY_ROOT


@pytest.fixture(autouse=True)
def _stub_execute_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    monkeypatch.setenv("FOUNDRY_VERIFY_ACCEPTANCE_DECISION", "pass")
    monkeypatch.delenv("FOUNDRY_EXECUTE_TEST_EXIT_CODE", raising=False)
    monkeypatch.delenv("FOUNDRY_EXECUTE_COMMIT_EXIT_CODE", raising=False)
    monkeypatch.delenv("FOUNDRY_EXECUTE_CODE_QUALITY_EXIT_CODE", raising=False)


def test_execute_commit_gate_passes_with_final_sha(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    authorize_execute_start(workspace, run_id)
    snapshot = advance_snapshot_to_execute_commit(workspace, run_id)
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
    gate = resolve_gate_at_node(snapshot, flow, run_dir, "execute.commit.gate", visit=visit)
    assert gate.get("ok") is True
    assert gate.get("decision") == "pass"


def test_verify_intake_gate_passes_with_intake_receipt(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    authorize_execute_start(workspace, run_id)
    snapshot = advance_snapshot_to_execute_commit(workspace, run_id)
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
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    authorize_execute_start(workspace, run_id)
    enable_verify_review(workspace, run_id)
    snapshot = advance_snapshot_to_execute_commit(workspace, run_id)
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
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    authorize_execute_start(workspace, run_id)
    enable_verify_review(workspace, run_id)
    snapshot = advance_snapshot_to_execute_commit(workspace, run_id)
    snapshot = advance_stub_run_to_completion(workspace, run_id, snapshot=snapshot)

    assert snapshot.get("status") == "completed"
    state = snapshot.get("state") or {}
    assert isinstance(state.get("deliver_handoff_message"), str)
    assert "ready to hand off" in state["deliver_handoff_message"].lower()

    status = get_run(workspace, run_id=run_id)
    assert status.get("ok") is True
    assert status.get("handoff_message")
