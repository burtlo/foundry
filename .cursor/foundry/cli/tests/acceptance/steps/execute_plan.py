"""Step definitions specific to execute_plan.feature."""

from __future__ import annotations

import json
import shutil

from pytest_bdd import when

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.agent.dispatch import ensure_execute_plan_request
from foundry_cli.engine.wait_state import set_run_wait
from foundry_cli.registry import load_registry
from foundry_cli.run_service import execute_start_durable
from foundry_cli.run_store import load_snapshot, save_snapshot
from tests.acceptance.helpers import invoke_foundry, run_dir, snapshot_path
from tests.conftest import FOUNDRY_ROOT
from tests.unit.git_workspace import ensure_clean_git_workspace


def _valid_plan_result(verdict: str) -> dict:
    if verdict == "BLOCKED":
        return {
            "summary": "BLOCKED: missing sealed plan.",
            "verdict": "BLOCKED",
            "execution_graph": {"schema_version": "1.0.0", "graph_id": "x", "work_items": [{"id": "wi", "title": "t"}]},
            "execute_brief_markdown": "n/a",
            "blockers": ["shape plan missing"],
        }
    return {
        "summary": "PROCEED: graph ready.",
        "verdict": "PROCEED",
        "execution_graph": {
            "schema_version": "1.0.0",
            "graph_id": "acceptance-run:execution-graph",
            "run_id": "acceptance-run",
            "work_items": [{"id": "wi-001", "title": "Implement AC", "owner": "feature-builder"}],
        },
        "execute_brief_markdown": "# Execute brief\n\n## AC\n\nTest AC.\n",
    }


def _advance_to_execute_plan(acceptance: dict) -> None:
    from pathlib import Path

    workspace = Path(acceptance["workspace"])
    shutil.copytree(
        FOUNDRY_ROOT / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
        dirs_exist_ok=True,
    )
    rd = run_dir(acceptance)
    run_id = acceptance["run_id"]
    acceptance["command"] = "gate decide"
    acceptance["extra_flags"] = ["--decision", "accept"]
    invoke_foundry(acceptance)
    assert acceptance["exit_code"] == 0
    acceptance["command"] = "run advance"
    acceptance["extra_flags"] = []
    invoke_foundry(acceptance)
    assert acceptance["exit_code"] == 0
    ensure_clean_git_workspace(workspace)
    start = execute_start_durable(workspace=workspace, bundle=FOUNDRY_ROOT, run_id=run_id)
    assert start.get("ok") is True
    snapshot = load_snapshot(rd)
    _, flow = load_registry(FOUNDRY_ROOT)
    for _ in range(8):
        ensure_clean_git_workspace(workspace)
        advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=FOUNDRY_ROOT,
            run_dir=rd,
            step_budget=6,
        )
        save_snapshot(rd, snapshot)
        active = snapshot.get("active_visit") or {}
        node_id = str(active.get("node_id") or "")
        wait = snapshot.get("wait")
        if node_id == "execute.plan":
            if isinstance(wait, dict) and wait.get("kind") == "agent":
                return
            if wait is None:
                return
        if node_id == "execute.build":
            raise AssertionError("advanced past execute.plan without stopping")
    raise AssertionError(f"did not reach execute.plan (active {node_id!r})")


@when("I prepare execute plan opened visit at execute.plan")
def prepare_execute_plan_opened(acceptance) -> None:
    _advance_to_execute_plan(acceptance)


@when("I prepare execute plan agent wait without auto submit")
def prepare_execute_plan_agent_wait(acceptance) -> None:
    from pathlib import Path

    _advance_to_execute_plan(acceptance)
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


def _active_agent_request_id(acceptance: dict) -> str:
    snap = json.loads(snapshot_path(acceptance).read_text(encoding="utf-8"))
    wait = snap.get("wait")
    assert isinstance(wait, dict), "expected agent wait on snapshot"
    request_ref = wait.get("request_ref")
    assert isinstance(request_ref, str) and request_ref.strip(), "missing agent request_ref"
    return request_ref


@when("I submit plan result with PROCEED verdict")
def submit_plan_proceed(acceptance) -> None:
    _invoke_agent_submit(acceptance, _valid_plan_result("PROCEED"))


@when("I submit plan result with BLOCKED verdict")
def submit_plan_blocked(acceptance) -> None:
    _invoke_agent_submit(acceptance, _valid_plan_result("BLOCKED"))


def _invoke_agent_submit(acceptance: dict, result: dict) -> None:
    request_id = _active_agent_request_id(acceptance)
    acceptance["command"] = "run agent submit"
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_flags"] = [
        "--request-id",
        request_id,
        "--result-json",
        json.dumps(result),
        "--local",
    ]
    acceptance["extra_argv"] = []
    invoke_foundry(acceptance)


@when('I invoke "visit plan complete" with json output')
def invoke_visit_plan_complete(acceptance) -> None:
    acceptance["command"] = "visit plan complete"
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = []
    invoke_foundry(acceptance)
