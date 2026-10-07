"""execute.branch git/mechanical advance (REL-008 pilot)."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.advance import advance_run
from foundry_cli.registry import load_registry
from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.git_workspace import ensure_clean_git_workspace
from tests.unit.implementation_flow_helpers import workspace_with_run_fixture

BUNDLE = FOUNDRY_ROOT
FIXTURE_EXECUTE_INTAKE_GATE = "porcelain-0007-v008-execute-intake-gate"


def test_execute_branch_advance_creates_feature_branch_after_intake_gate(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_EXECUTE_INTAKE_GATE)
    ensure_clean_git_workspace(workspace)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    gate_advance = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=1,
    )
    assert gate_advance.get("reason") == "engine_gate_resolved"
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") == "execute.branch"

    branch_advance = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=1,
    )
    assert branch_advance.get("reason") == "execute_branch_complete"
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") == "execute.plan"
    state = snapshot.get("state") or {}
    assert state.get("feature_branch", "").startswith("foundry/")
    assert state.get("execution_graph_id")
