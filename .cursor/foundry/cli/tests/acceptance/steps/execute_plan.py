"""Step definitions specific to execute_plan.feature."""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import when

from foundry_cli.engine.agent.dispatch import ensure_execute_plan_request
from foundry_cli.engine.wait_state import set_run_wait
from foundry_cli.registry import load_registry
from foundry_cli.run_store import load_snapshot, save_snapshot
from tests.acceptance.acceptance_agent_steps import invoke_agent_submit, invoke_visit_lifecycle_complete
from tests.acceptance.acceptance_flow_helpers import advance_acceptance_run_to_execute_plan
from tests.acceptance.helpers import run_dir
from tests.conftest import FOUNDRY_ROOT
from tests.unit.execute_advance_helpers import stub_execute_plan_result


def _plan_result(verdict: str, run_id: str) -> dict:
    if verdict == "BLOCKED":
        return stub_execute_plan_result(
            run_id,
            summary="BLOCKED: missing sealed plan.",
            verdict="BLOCKED",
            execution_graph={
                "schema_version": "1.0.0",
                "graph_id": "x",
                "work_items": [{"id": "wi", "title": "t"}],
            },
            execute_brief_markdown="n/a",
            blockers=["shape plan missing"],
        )
    return stub_execute_plan_result(
        run_id,
        summary="PROCEED: graph ready.",
        execute_brief_markdown="# Execute brief\n\n## AC\n\nTest AC.\n",
        execution_graph={
            "schema_version": "1.0.0",
            "graph_id": f"{run_id}:execution-graph",
            "run_id": run_id,
            "work_items": [{"id": "wi-001", "title": "Implement AC", "owner": "feature-builder"}],
        },
    )


@when("I prepare execute plan opened visit at execute.plan")
def prepare_execute_plan_opened(acceptance) -> None:
    advance_acceptance_run_to_execute_plan(acceptance)


@when("I prepare execute plan agent wait without auto submit")
def prepare_execute_plan_agent_wait(acceptance) -> None:
    advance_acceptance_run_to_execute_plan(acceptance)
    workspace = Path(acceptance["workspace"])
    rd = run_dir(acceptance)
    snapshot = load_snapshot(rd)
    _, flow = load_registry(FOUNDRY_ROOT)
    visit = snapshot["active_visit"]
    request_id = ensure_execute_plan_request(
        snapshot,
        visit,
        flow,
        foundry_bundle=FOUNDRY_ROOT,
        workspace=workspace,
        run_dir=rd,
    )
    set_run_wait(
        snapshot,
        kind="agent",
        visit_id=str(visit["id"]),
        summary="Execute plan judgment required",
        request_ref=request_id,
    )
    save_snapshot(rd, snapshot)


@when("I submit plan result with PROCEED verdict")
def submit_plan_proceed(acceptance) -> None:
    run_id = str(acceptance.get("run_id") or "acceptance-run")
    invoke_agent_submit(acceptance, _plan_result("PROCEED", run_id))


@when("I submit plan result with BLOCKED verdict")
def submit_plan_blocked(acceptance) -> None:
    run_id = str(acceptance.get("run_id") or "acceptance-run")
    invoke_agent_submit(acceptance, _plan_result("BLOCKED", run_id))


@when('I invoke "visit plan complete" with json output')
def invoke_visit_plan_complete(acceptance) -> None:
    invoke_visit_lifecycle_complete(acceptance, "visit plan complete")
