"""Shared helpers for advancing execute workflow slices through judgment steps."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.engine.agent.dispatch import (
    ensure_agent_request,
    visit_has_accepted_task,
    visit_has_accepted_task_result,
)
from foundry_cli.engine.agent.submit import submit_agent_result
from foundry_cli.engine.agent.tasks import EXECUTE_PLAN_TASK_ID, VERIFY_ACCEPTANCE_TASK_ID


def stub_execute_plan_result(run_id: str = "test-run", **overrides: Any) -> dict[str, Any]:
    graph_id = f"{run_id}:execution-graph"
    body: dict[str, Any] = {
        "summary": "PROCEED: graph ready.",
        "verdict": "PROCEED",
        "execution_graph": {
            "schema_version": "1.0.0",
            "graph_id": graph_id,
            "run_id": run_id,
            "work_items": [{"id": "wi-001", "title": "Implement AC", "owner": "feature-builder"}],
        },
        "execute_brief_markdown": "# Execute brief\n\n## AC\n\nShip it.\n",
    }
    body.update(overrides)
    return body


def stub_verify_acceptance_result(**overrides: Any) -> dict[str, Any]:
    import os

    decision = (os.environ.get("FOUNDRY_VERIFY_ACCEPTANCE_DECISION") or "pass").strip().lower()
    if decision not in {"pass", "replan", "reshape", "rework_execute"}:
        decision = "pass"
    evidence_ok = decision == "pass"
    body: dict[str, Any] = {
        "summary": f"Stub verify acceptance ({decision}).",
        "gate_decision": decision,
        "evidence_ok": evidence_ok,
        "items": [
            {
                "criterion": "Approved acceptance criteria",
                "status": "met" if evidence_ok else "not_met",
                "basis": "Test stub judgment.",
            }
        ],
    }
    body.update(overrides)
    return body


def submit_verify_acceptance_if_waiting(
    snapshot: dict[str, Any],
    *,
    visit: dict[str, Any],
    flow: dict[str, Any],
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> bool:
    """Submit verify.acceptance judgment when the visit is waiting on agent. Returns True if submitted."""
    if str(visit.get("node_id")) != VERIFY_ACCEPTANCE_TASK_ID:
        return False
    visit_id = str(visit.get("id") or "")
    if visit_has_accepted_task_result(snapshot, visit_id=visit_id, task_id=VERIFY_ACCEPTANCE_TASK_ID):
        return False
    wait = snapshot.get("wait")
    if not (isinstance(wait, dict) and wait.get("kind") == "agent"):
        return False
    request_ref = wait.get("request_ref")
    if not isinstance(request_ref, str) or not request_ref.strip():
        request_ref = ensure_agent_request(
            snapshot,
            visit,
            flow,
            task_id=VERIFY_ACCEPTANCE_TASK_ID,
            foundry_bundle=foundry_bundle,
            workspace=workspace,
            run_dir=run_dir,
        )
    submit_agent_result(
        snapshot,
        request_id=request_ref,
        result=stub_verify_acceptance_result(),
        foundry_bundle=foundry_bundle,
        visit=visit,
        run_dir=run_dir,
        workspace=workspace,
    )
    return True


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
    if visit_has_accepted_task(
        snapshot,
        visit_id=visit_id,
        task_id=EXECUTE_PLAN_TASK_ID,
        foundry_bundle=foundry_bundle,
    ):
        return False
    wait = snapshot.get("wait")
    if not (isinstance(wait, dict) and wait.get("kind") == "agent"):
        return False
    request_ref = wait.get("request_ref")
    if not isinstance(request_ref, str) or not request_ref.strip():
        request_ref = ensure_agent_request(
            snapshot,
            visit,
            flow,
            task_id=EXECUTE_PLAN_TASK_ID,
            foundry_bundle=foundry_bundle,
            workspace=workspace,
            run_dir=run_dir,
        )
    submit_agent_result(
        snapshot,
        request_id=request_ref,
        result=stub_execute_plan_result(
            str(snapshot.get("run_id") or "test-run"),
            summary="PROCEED: graph ready (test stub).",
            execute_brief_markdown="# Execute brief\n\n## AC\n\nStub brief.\n",
        ),
        foundry_bundle=foundry_bundle,
        visit=visit,
        run_dir=run_dir,
        workspace=workspace,
    )
    return True
