"""Step definitions specific to shape_present.feature."""

from __future__ import annotations

from pytest_bdd import when

from foundry_cli.engine.agent.dispatch import ensure_shape_present_request
from tests.acceptance.acceptance_agent_steps import (
    invoke_agent_submit,
    invoke_visit_lifecycle_complete,
    set_shape_agent_wait_without_submit,
)
from tests.unit.shape_flow_helpers import valid_presentation_result


def _presentation_result(verdict: str) -> dict:
    if verdict == "BLOCKED":
        return valid_presentation_result(
            summary="BLOCKED: draft_ac too vague to present.",
            verdict="BLOCKED",
            presented_ac="n/a",
            presentation_markdown="n/a",
            blockers=["draft_ac too vague to present"],
        )
    return valid_presentation_result(
        summary="PROCEED: presentation ready to publish.",
        presented_ac="User can publish presentation markdown.",
        presentation_markdown=(
            "# Shape plan presentation\n\n"
            "## Acceptance criteria\n\n"
            "User can publish presentation markdown.\n"
        ),
    )


@when("I prepare shape present agent wait without auto submit")
def prepare_shape_present_agent_wait(acceptance) -> None:
    set_shape_agent_wait_without_submit(
        acceptance,
        ensure_request=ensure_shape_present_request,
        summary="Shape presentation judgment required",
    )


@when("I submit presentation result with PROCEED verdict")
def submit_presentation_proceed(acceptance) -> None:
    invoke_agent_submit(acceptance, _presentation_result("PROCEED"))


@when("I submit presentation result with BLOCKED verdict")
def submit_presentation_blocked(acceptance) -> None:
    invoke_agent_submit(acceptance, _presentation_result("BLOCKED"))


@when('I invoke "visit present complete" with json output')
def invoke_visit_present_complete(acceptance) -> None:
    invoke_visit_lifecycle_complete(acceptance, "visit present complete")
