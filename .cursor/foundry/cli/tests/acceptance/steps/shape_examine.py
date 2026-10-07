"""Step definitions specific to shape_examine.feature."""

from __future__ import annotations

from pytest_bdd import when

from foundry_cli.engine.agent.dispatch import ensure_shape_examine_request
from tests.acceptance.acceptance_agent_steps import (
    invoke_agent_submit,
    invoke_visit_lifecycle_complete,
    set_shape_agent_wait_without_submit,
)
from tests.acceptance.helpers import invoke_foundry
from tests.unit.shape_flow_helpers import valid_examination_result


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
    set_shape_agent_wait_without_submit(
        acceptance,
        ensure_request=ensure_shape_examine_request,
        summary="Shape examination judgment required",
    )


@when("I submit examination result with no open questions")
def submit_examination_no_questions(acceptance) -> None:
    invoke_agent_submit(acceptance, valid_examination_result(questions=[]))


@when("I submit examination result with one open question")
def submit_examination_one_question(acceptance) -> None:
    result = valid_examination_result(
        questions=[{"id": "q-scope", "text": "Which API surface?", "why_needed": "Scope"}],
    )
    invoke_agent_submit(acceptance, result)


@when("I invoke visit examine complete with json output")
def invoke_visit_examine_complete(acceptance) -> None:
    invoke_visit_lifecycle_complete(acceptance, "visit examine complete")


@when("I invoke visit examine complete with open questions gate path")
def invoke_visit_examine_complete_gate(acceptance) -> None:
    invoke_visit_lifecycle_complete(acceptance, "visit examine complete", extra_flags=["--with-open-questions"])
