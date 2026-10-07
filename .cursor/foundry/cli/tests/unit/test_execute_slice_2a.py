"""Workflow-02 slice 2A: execute.intake through execute.plan."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.gates import resolve_engine_gate_decision
from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
from foundry_cli.registry import load_registry
from foundry_cli.run_service import execute_start_durable
from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import FIXTURE_PORCELAIN_RECORD_GATE, TEST_RUN_UUID
from tests.unit.git_workspace import ensure_clean_git_workspace
from tests.unit.implementation_flow_helpers import invoke_foundry_cli, workspace_with_run_fixture
from tests.unit.receipt_fixtures import (
    intake_receipt_body,
    minimal_engine_gate_flow,
    opened_gate_visit,
    prepare_run_dir,
    snapshot_with_sealed_receipt,
)

BUNDLE = FOUNDRY_ROOT


def _authorize_execute(workspace: Path, run_id: str) -> None:
    decide = invoke_foundry_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
    assert decide.returncode == 0, decide.stderr + decide.stdout
    advance = invoke_foundry_cli(workspace, "run", "advance", "--run", run_id)
    assert advance.returncode == 0, advance.stderr + advance.stdout
    body = json.loads(advance.stdout)
    assert body.get("active_node_id") == "execute.start"
    ensure_clean_git_workspace(workspace)
    start = execute_start_durable(workspace=workspace, bundle=BUNDLE, run_id=run_id)
    assert start.get("ok") is True, start
    assert start.get("active_node_id") == "execute.intake"


def test_execute_intake_gate_passes_on_passed_receipt(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    _authorize_execute(workspace, run_id)
    ensure_clean_git_workspace(workspace)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    result = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=12,
    )
    assert result["reason"] != "execution_error"
    assert snapshot.get("status") == "running"
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") in {"execute.branch", "execute.plan", "execute.build"}
    state = snapshot.get("state") or {}
    assert state.get("feature_branch", "").startswith("foundry/")
    assert state.get("execution_graph_id")

    gate_visit = next(
        (v for v in snapshot.get("visits", []) if v.get("node_id") == "execute.intake.gate"),
        None,
    )
    assert gate_visit is not None
    assert gate_visit.get("decision") == "pass"

    if active.get("node_id") == "execute.build":
        wait = snapshot.get("wait")
        assert wait is None


def test_boundary_wait_execute_intake_allows_host_advance(tmp_path: Path) -> None:
    from foundry_cli.engine.advance import _boundary_wait_for_visit

    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    visit = {
        "id": "v-intake",
        "node_id": "execute.intake",
        "kind": "step",
        "lifecycle": "opened",
    }
    wait = _boundary_wait_for_visit(
        snapshot={"status": "running", "ledger": [], "wait": None},
        visit=visit,
        flow=flow,
        foundry_bundle=BUNDLE,
        workspace=workspace,
        run_dir=run_dir,
    )
    assert wait is None


def test_execute_intake_gate_rejects_blocked_receipt(tmp_path: Path) -> None:
    intake_visit_id = "v-ei"
    run_dir = prepare_run_dir(tmp_path)
    receipt = intake_receipt_body(
        "execute.intake",
        status="blocked",
        receipt_id="00000000-0000-4000-8000-000000000010",
        checks=[{"id": "validate-manifest", "status": "pass"}],
    )
    snapshot = snapshot_with_sealed_receipt(
        run_dir,
        visit_id=intake_visit_id,
        step_node_id="execute.intake",
        schema=INTAKE_RECEIPT_SCHEMA,
        receipt=receipt,
        run_id=TEST_RUN_UUID,
    )
    visit = opened_gate_visit("v-g", "execute.intake.gate")
    flow = minimal_engine_gate_flow("execute.intake.gate", ["pass"])
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    assert result["ok"] is False
    assert result["code"] == "EVIDENCE_MISSING"
