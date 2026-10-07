"""Unit tests for visit plan complete executor."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.execute_step_executor import run_execute_plan_complete
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.execute_step_fixtures import assert_execute_step_allow_cli, opened_execute_plan_run
from tests.unit.shape_flow_helpers import shape_test_workspace

BUNDLE = FOUNDRY_ROOT
NODE_EXECUTE_PLAN = "execute.plan"


def test_implementation_flow_execute_plan_allow_cli() -> None:
    _, flow = load_registry(BUNDLE)
    assert_execute_step_allow_cli(
        flow,
        NODE_EXECUTE_PLAN,
        ["run.agent.submit", "visit.plan.complete"],
    )


def test_plan_complete_happy_path(tmp_path: Path) -> None:
    workspace, run_dir, snapshot, visit, flow = opened_execute_plan_run(tmp_path)
    result = run_execute_plan_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is True
    assert result["next_node_id"] == "execute.build"
    graph_path = run_dir / "artifacts" / str(visit["id"]) / "execution-graph.json"
    assert graph_path.is_file()
    brief_path = run_dir / "artifacts" / str(visit["id"]) / "execute-brief.md"
    assert brief_path.is_file()


def test_plan_complete_judgment_missing(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "plan-missing"
    run_dir.mkdir(parents=True)
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "plan-missing",
        "status": "running",
        "visits": [],
        "ledger": [],
        "active_visit": {
            "id": "v-plan",
            "node_id": NODE_EXECUTE_PLAN,
            "kind": "step",
            "lifecycle": "opened",
        },
    }
    visit = snapshot["active_visit"]
    result = run_execute_plan_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is False
    assert result["code"] == "JUDGMENT_MISSING"
