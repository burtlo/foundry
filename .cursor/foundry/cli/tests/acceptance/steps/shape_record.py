"""Step definitions specific to shape_record.feature."""

from __future__ import annotations

import json

from pytest_bdd import when

from foundry_cli.engine.agent.dispatch import ensure_shape_record_request
from foundry_cli.engine.wait_state import set_run_wait
from foundry_cli.registry import load_registry
from foundry_cli.run_store import load_snapshot, save_snapshot
from tests.acceptance.helpers import invoke_foundry, run_dir, snapshot_path
from tests.conftest import FOUNDRY_ROOT


def _active_agent_request_id(acceptance: dict) -> str:
    snap = json.loads(snapshot_path(acceptance).read_text(encoding="utf-8"))
    wait = snap.get("wait")
    assert isinstance(wait, dict), "expected agent wait on snapshot"
    request_ref = wait.get("request_ref")
    assert isinstance(request_ref, str) and request_ref.strip(), "missing agent request_ref"
    return request_ref


def _valid_record_result(verdict: str) -> dict:
    if verdict == "BLOCKED":
        return {
            "summary": "BLOCKED: presented_ac too vague to freeze.",
            "verdict": "BLOCKED",
            "approved_ac": "n/a",
            "plan_markdown": "n/a",
            "blockers": ["presented_ac too vague to freeze"],
        }
    return {
        "summary": "PROCEED: plan ready to publish.",
        "verdict": "PROCEED",
        "approved_ac": "User can publish plan markdown.",
        "plan_markdown": (
            "# Living plan\n\n"
            "## Scope\n\n"
            "Recorded plan for tests.\n\n"
            "## Acceptance criteria\n\n"
            "User can publish plan markdown.\n"
        ),
    }


@when("I prepare shape record agent wait without auto submit")
def prepare_shape_record_agent_wait(acceptance) -> None:
    from pathlib import Path

    workspace = Path(acceptance["workspace"])
    rd = run_dir(acceptance)
    snapshot = load_snapshot(rd)
    _, flow = load_registry(FOUNDRY_ROOT)
    visit = snapshot["active_visit"]
    request_id = ensure_shape_record_request(
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
        summary="Shape record judgment required",
        request_ref=request_id,
    )
    save_snapshot(rd, snapshot)


@when("I submit record result with PROCEED verdict")
def submit_record_proceed(acceptance) -> None:
    _invoke_agent_submit(acceptance, _valid_record_result("PROCEED"))


@when("I submit record result with BLOCKED verdict")
def submit_record_blocked(acceptance) -> None:
    _invoke_agent_submit(acceptance, _valid_record_result("BLOCKED"))


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


@when('I invoke "visit record complete" with json output')
def invoke_visit_record_complete(acceptance) -> None:
    acceptance["command"] = "visit record complete"
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = []
    invoke_foundry(acceptance)
