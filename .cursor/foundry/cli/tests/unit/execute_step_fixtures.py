"""Opened execute-step runs and flow contract assertions."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from foundry_cli.engine.agent.submit import submit_agent_result
from foundry_cli.registry import load_registry
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import IMPLEMENTATION_FLOW
from tests.unit.execute_advance_helpers import stub_execute_plan_result
from tests.unit.git_workspace import ensure_clean_git_workspace

BUNDLE = FOUNDRY_ROOT


def flow_node(flow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in flow["nodes"] if node.get("id") == node_id)


def assert_execute_step_engine_owned(
    flow: dict[str, Any],
    node_id: str,
    *,
    allow_state: list[str] | None = None,
    allow_state_contains: tuple[str, ...] = (),
    forbid_cli: bool = False,
    artifact_id: str | None = None,
) -> None:
    node = flow_node(flow, node_id)
    assert "instructions" not in node
    assert "worker" not in node
    allow = node.get("allow") or {}
    if forbid_cli:
        assert "cli" not in allow
    else:
        assert "files" not in allow
    if allow_state is not None:
        assert allow.get("state") == allow_state
    if allow_state_contains:
        keys = allow.get("state") or []
        for key in allow_state_contains:
            assert key in keys
    if artifact_id is not None:
        artifacts = node.get("produces", {}).get("artifacts") or []
        assert any(a.get("id") == artifact_id for a in artifacts)


def assert_execute_step_allow_cli(flow: dict[str, Any], node_id: str, cli: list[str]) -> None:
    node = flow_node(flow, node_id)
    assert node["allow"]["cli"] == cli
    assert "worker" not in node


def opened_execute_step_run(
    tmp_path: Path,
    *,
    node_id: str,
    run_id: str,
    visit_id: str,
    state: dict[str, Any],
    with_receipts_dir: bool = True,
    workspace: Path | None = None,
) -> tuple[Path, Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return workspace, run_dir, snapshot, visit, flow with an opened step visit."""
    ws = workspace if workspace is not None else tmp_path / "app"
    if workspace is None:
        ws.mkdir()
    run_dir = ws / ".foundry" / "runs" / run_id
    run_dir.mkdir(parents=True)
    if with_receipts_dir:
        (run_dir / "receipts").mkdir(exist_ok=True)
    snapshot: dict[str, Any] = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "status": "running",
        "flow_id": IMPLEMENTATION_FLOW,
        "state": state,
        "visits": [],
        "ledger": [],
        "active_visit": {
            "id": visit_id,
            "node_id": node_id,
            "kind": "step",
            "lifecycle": "opened",
        },
    }
    visit = snapshot["active_visit"]
    _, flow = load_registry(BUNDLE)
    return ws, run_dir, snapshot, visit, flow


def opened_execute_commit_run(tmp_path: Path) -> tuple[Path, Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    workspace = tmp_path / "app"
    workspace.mkdir()
    (workspace / "README.md").write_text("commit step test\n", encoding="utf-8")
    ensure_clean_git_workspace(workspace)
    subprocess.run(
        ["git", "checkout", "-b", "foundry/test"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )
    return opened_execute_step_run(
        tmp_path,
        node_id="execute.commit",
        run_id="test-step",
        visit_id="v-commit",
        state={
            "execution_graph_id": "test-step:execution-graph",
            "feature_branch": "foundry/test",
        },
        workspace=workspace,
    )


def opened_execute_plan_run(tmp_path: Path) -> tuple[Path, Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    workspace, run_dir, snapshot, visit, flow = opened_execute_step_run(
        tmp_path,
        node_id="execute.plan",
        run_id="plan-test",
        visit_id="v-plan",
        state={
            "execution_graph_id": "test-run:execution-graph",
            "feature_branch": "foundry/test",
            "approved_ac": "Ship it.",
        },
        with_receipts_dir=False,
    )
    request_id = "ar_testplan0001"
    snapshot["agent_requests"] = {
        request_id: {
            "request_id": request_id,
            "visit_id": visit["id"],
            "task_id": "execute.plan",
            "status": "requested",
            "output_schema": "registry:schemas/execute-plan-result.schema.json",
        }
    }
    snapshot["wait"] = {
        "kind": "agent",
        "visit_id": visit["id"],
        "request_ref": request_id,
    }
    submit_agent_result(
        snapshot,
        request_id=request_id,
        result=stub_execute_plan_result("test-run"),
        foundry_bundle=BUNDLE,
        visit=visit,
        run_dir=run_dir,
        workspace=workspace,
    )
    save_snapshot(run_dir, snapshot)
    return workspace, run_dir, snapshot, visit, flow
