"""REL-011 (G5): blocked intake operator wait and recovery (T3, T4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.blocked_intake import BLOCKED_INTAKE_STATUS_CODE
from foundry_cli.engine.gates import resolve_engine_gate_decision
from foundry_cli.ledger import count_events
from foundry_cli.registry import load_registry
from foundry_cli.run_service import execute_start_durable
from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import FIXTURE_PORCELAIN_RECORD_GATE
from tests.unit.git_workspace import ensure_clean_git_workspace
from tests.unit.implementation_flow_helpers import (
    advance_snapshot_through_stub_execute,
    invoke_foundry_cli,
    stub_record_gate_run,
    workspace_with_run_fixture,
)
from tests.unit.test_verify_evidence import VERIFY_INTAKE_NODE
from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA

BUNDLE = FOUNDRY_ROOT

pytestmark = pytest.mark.usefixtures("stub_implementation_execute")


def _reach_execute_intake(workspace: Path, run_id: str) -> None:
    decide = invoke_foundry_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
    assert decide.returncode == 0
    advance = invoke_foundry_cli(workspace, "run", "advance", "--run", run_id)
    assert advance.returncode == 0
    ensure_clean_git_workspace(workspace)
    start = execute_start_durable(workspace=workspace, bundle=BUNDLE, run_id=run_id)
    assert start.get("ok") is True
    assert start.get("active_node_id") == "execute.intake"


def test_execute_intake_blocked_then_recovery_t3(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    _reach_execute_intake(workspace, run_id)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    state = snapshot.setdefault("state", {})
    saved_approved_ac = state.get("approved_ac") if isinstance(state, dict) else None
    saved_plan_path = state.get("plan_path") if isinstance(state, dict) else None
    saved_digest = state.get("approved_ac_digest") if isinstance(state, dict) else None
    saved_version = state.get("approved_ac_version") if isinstance(state, dict) else None
    if isinstance(state, dict):
        state.pop("approved_ac", None)

    blocked = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=1,
    )
    assert blocked.get("reason") == "intake_blocked"
    assert snapshot.get("halt_reason") == BLOCKED_INTAKE_STATUS_CODE
    wait = snapshot.get("wait") or {}
    assert wait.get("kind") == "operator"
    visit_id = str((snapshot.get("active_visit") or {}).get("id", ""))
    before = count_events(
        snapshot,
        "receipt.linked",
        visit_id=visit_id,
        schema=INTAKE_RECEIPT_SCHEMA,
    )

    still_blocked = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=1,
    )
    assert still_blocked.get("reason") == "wait"
    after = count_events(
        snapshot,
        "receipt.linked",
        visit_id=visit_id,
        schema=INTAKE_RECEIPT_SCHEMA,
    )
    assert after == before

    if isinstance(state, dict):
        if saved_approved_ac is not None:
            state["approved_ac"] = saved_approved_ac
        if saved_version is not None:
            state["approved_ac_version"] = saved_version
        else:
            state["approved_ac_version"] = 1
        if saved_digest:
            state["approved_ac_digest"] = saved_digest
        else:
            state["approved_ac_digest"] = "a" * 64
        if saved_plan_path:
            state["plan_path"] = saved_plan_path

    recovered = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=8,
    )
    assert recovered.get("reason") != "intake_blocked"
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") in {
        "execute.intake.gate",
        "execute.branch",
        "execute.plan",
        "execute.build",
    }
    gate_visit = next(
        (v for v in snapshot.get("visits", []) if v.get("node_id") == "execute.intake.gate"),
        None,
    )
    if gate_visit is None:
        assert active.get("node_id") != "execute.intake"
    else:
        assert gate_visit.get("decision") == "pass" or active.get("node_id") != "execute.intake"


def test_verify_intake_blocked_then_recovery_t4(tmp_path: Path) -> None:
    run = stub_record_gate_run(tmp_path, advance_to="execute.commit")
    workspace, run_id = run.workspace, run.run_id
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = advance_snapshot_through_stub_execute(workspace, run_id, stop_at=VERIFY_INTAKE_NODE)
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") == VERIFY_INTAKE_NODE
    assert active.get("lifecycle") == "opened"
    state = snapshot.setdefault("state", {})
    assert isinstance(state, dict)
    saved_branch = state.get("feature_branch")
    state.pop("feature_branch", None)
    snapshot["status"] = "running"

    blocked = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=1,
    )
    assert blocked.get("reason") == "intake_blocked"
    assert snapshot.get("status") == "running"

    if isinstance(saved_branch, str) and saved_branch.strip():
        state["feature_branch"] = saved_branch
    else:
        state["feature_branch"] = "foundry/test-feature"
    recovered = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=4,
    )
    assert recovered.get("reason") != "intake_blocked"
    gate_visit = None
    for v in snapshot.get("visits", []):
        if v.get("node_id") == "verify.intake.gate":
            gate_visit = v
            break
    assert gate_visit is not None
    result = resolve_engine_gate_decision(
        snapshot,
        gate_visit,
        flow,
        run_dir=run_dir,
    )
    assert result.get("ok") is True
    assert result.get("decision") == "pass"
