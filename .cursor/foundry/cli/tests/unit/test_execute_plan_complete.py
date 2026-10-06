"""Unit tests for visit plan complete executor."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.engine.agent.submit import submit_agent_result
from foundry_cli.engine.execute_step_executor import run_execute_plan_complete
from foundry_cli.registry import load_registry
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT
NODE_EXECUTE_PLAN = "execute.plan"


def _valid_plan_result(**overrides: object) -> dict:
    body = {
        "summary": "PROCEED: graph ready.",
        "verdict": "PROCEED",
        "execution_graph": {
            "schema_version": "1.0.0",
            "graph_id": "test-run:execution-graph",
            "run_id": "test-run",
            "work_items": [{"id": "wi-001", "title": "Build feature", "owner": "feature-builder"}],
        },
        "execute_brief_markdown": "# Execute brief\n\n## AC\n\nShip it.\n",
    }
    body.update(overrides)
    return body


def _plan_opened_run(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    workspace = tmp_path / "app"
    workspace.mkdir()
    run_dir = workspace / ".foundry" / "runs" / "plan-test"
    run_dir.mkdir(parents=True)
    visit_id = "v-plan"
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "plan-test",
        "status": "running",
        "flow_id": "implementation",
        "state": {
            "execution_graph_id": "test-run:execution-graph",
            "feature_branch": "foundry/test",
            "approved_ac": "Ship it.",
        },
        "visits": [],
        "ledger": [],
        "agent_requests": {},
        "active_visit": {
            "id": visit_id,
            "node_id": NODE_EXECUTE_PLAN,
            "kind": "step",
            "lifecycle": "opened",
        },
        "wait": {
            "kind": "agent",
            "visit_id": visit_id,
            "request_ref": "ar_testplan0001",
        },
    }
    request_id = "ar_testplan0001"
    snapshot["agent_requests"][request_id] = {
        "request_id": request_id,
        "visit_id": visit_id,
        "task_id": NODE_EXECUTE_PLAN,
        "status": "requested",
        "output_schema": "registry:schemas/execute-plan-result.schema.json",
    }
    visit = snapshot["active_visit"]
    _, flow = load_registry(BUNDLE)
    submit_agent_result(
        snapshot,
        request_id=request_id,
        result=_valid_plan_result(),
        foundry_bundle=BUNDLE,
        visit=visit,
        run_dir=run_dir,
        workspace=workspace,
    )
    save_snapshot(run_dir, snapshot)
    return run_dir, snapshot, visit, flow


def test_implementation_flow_execute_plan_allow_cli() -> None:
    _, flow = load_registry(BUNDLE)
    plan_node = next(node for node in flow["nodes"] if node.get("id") == NODE_EXECUTE_PLAN)
    assert plan_node["allow"]["cli"] == ["run.agent.submit", "visit.plan.complete"]
    assert "worker" not in plan_node


def test_plan_complete_happy_path(tmp_path: Path) -> None:
    run_dir, snapshot, visit, flow = _plan_opened_run(tmp_path)
    workspace = tmp_path / "app"
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
    workspace = tmp_path / "app"
    workspace.mkdir()
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
