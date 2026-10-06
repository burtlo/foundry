"""Shared helpers for advancing execute workflow slices through judgment steps."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.engine.agent.dispatch import ensure_execute_plan_request, visit_has_accepted_proceed_plan
from foundry_cli.engine.agent.submit import submit_agent_result


def _stub_execute_plan_result(run_id: str) -> dict[str, Any]:
    graph_id = f"{run_id}:execution-graph"
    return {
        "summary": "PROCEED: graph ready (test stub).",
        "verdict": "PROCEED",
        "execution_graph": {
            "schema_version": "1.0.0",
            "graph_id": graph_id,
            "run_id": run_id,
            "work_items": [{"id": "wi-001", "title": "Implement AC", "owner": "feature-builder"}],
        },
        "execute_brief_markdown": "# Execute brief\n\n## AC\n\nStub brief.\n",
    }


def submit_execute_plan_proceed_if_waiting(
    snapshot: dict[str, Any],
    *,
    visit: dict[str, Any],
    flow: dict[str, Any],
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> bool:
    """Submit PROCEED plan judgment when execute.plan is waiting on agent. Returns True if submitted."""
    if str(visit.get("node_id")) != "execute.plan":
        return False
    visit_id = str(visit.get("id") or "")
    if visit_has_accepted_proceed_plan(snapshot, visit_id=visit_id):
        return False
    wait = snapshot.get("wait")
    if not (isinstance(wait, dict) and wait.get("kind") == "agent"):
        return False
    request_ref = wait.get("request_ref")
    if not isinstance(request_ref, str) or not request_ref.strip():
        request_ref = ensure_execute_plan_request(
            snapshot,
            visit,
            flow,
            foundry_bundle=foundry_bundle,
            workspace=workspace,
            run_dir=run_dir,
        )
    submit_agent_result(
        snapshot,
        request_id=request_ref,
        result=_stub_execute_plan_result(str(snapshot.get("run_id") or "test-run")),
        foundry_bundle=foundry_bundle,
        visit=visit,
        run_dir=run_dir,
        workspace=workspace,
    )
    return True
