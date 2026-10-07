"""Step definitions specific to shape_examine.feature."""

from __future__ import annotations

import json
from pathlib import Path

from pytest_bdd import then, when

from foundry_cli.engine.agent.dispatch import ensure_shape_examine_request
from foundry_cli.engine.wait_state import set_run_wait
from foundry_cli.registry import load_registry
from foundry_cli.run_store import load_snapshot, save_snapshot
from tests.acceptance.helpers import invoke_foundry, run_dir, snapshot_path
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import valid_examination_result


def _active_agent_request_id(acceptance: dict) -> str:
    snap = json.loads(snapshot_path(acceptance).read_text(encoding="utf-8"))
    wait = snap.get("wait")
    assert isinstance(wait, dict), "expected agent wait on snapshot"
    request_ref = wait.get("request_ref")
    assert isinstance(request_ref, str) and request_ref.strip(), "missing agent request_ref"
    return request_ref


@when("I dispatch shape examine agent wait via run advance")
def dispatch_shape_examine_agent(acceptance) -> None:
    """Advance through stub agent dispatch+accept (no open questions)."""
    acceptance["command"] = "run advance"
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = ["--local"]
    invoke_foundry(acceptance)


@when("I prepare shape examine agent wait without auto submit")
def prepare_shape_examine_agent_wait(acceptance) -> None:
    workspace = Path(acceptance["workspace"])
    rd = run_dir(acceptance)
    snapshot = load_snapshot(rd)
    _, flow = load_registry(FOUNDRY_ROOT)
    visit = snapshot["active_visit"]
    request_id = ensure_shape_examine_request(
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
        summary="Shape examination judgment required",
        request_ref=request_id,
    )
    save_snapshot(rd, snapshot)


@when("I submit examination result with no open questions")
def submit_examination_no_questions(acceptance) -> None:
    result = valid_examination_result(questions=[])
    _invoke_agent_submit(acceptance, result)


@when("I submit examination result with one open question")
def submit_examination_one_question(acceptance) -> None:
    result = valid_examination_result(
        questions=[{"id": "q-scope", "text": "Which API surface?", "why_needed": "Scope"}],
    )
    _invoke_agent_submit(acceptance, result)


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


@when("I invoke visit examine complete with json output")
def invoke_visit_examine_complete(acceptance) -> None:
    acceptance["command"] = "visit examine complete"
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = []
    invoke_foundry(acceptance)


@when("I invoke visit examine complete with open questions gate path")
def invoke_visit_examine_complete_gate(acceptance) -> None:
    acceptance["command"] = "visit examine complete"
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = ["--with-open-questions"]
    invoke_foundry(acceptance)
