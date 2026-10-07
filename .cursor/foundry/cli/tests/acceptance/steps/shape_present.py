"""Step definitions specific to shape_present.feature."""

from __future__ import annotations

from pytest_bdd import when

from foundry_cli.engine.agent.dispatch import ensure_shape_present_request
from tests.acceptance.acceptance_agent_steps import (
    invoke_agent_submit,
    invoke_visit_lifecycle_complete,
    set_agent_wait_without_submit,
)
from tests.acceptance.acceptance_shape_judgments import acceptance_presentation_result


@when("I prepare shape present agent wait without auto submit")
def prepare_shape_present_agent_wait(acceptance) -> None:
    set_agent_wait_without_submit(
        acceptance,
        ensure_request=ensure_shape_present_request,
        summary="Shape presentation judgment required",
    )


@when("I submit presentation result with PROCEED verdict")
def submit_presentation_proceed(acceptance) -> None:
    invoke_agent_submit(acceptance, acceptance_presentation_result("PROCEED"))


@when("I submit presentation result with BLOCKED verdict")
def submit_presentation_blocked(acceptance) -> None:
    invoke_agent_submit(acceptance, acceptance_presentation_result("BLOCKED"))


@when('I invoke "visit present complete" with json output')
def invoke_visit_present_complete(acceptance) -> None:
    invoke_visit_lifecycle_complete(acceptance, "visit present complete")
