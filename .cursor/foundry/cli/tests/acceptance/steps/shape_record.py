"""Step definitions specific to shape_record.feature."""

from __future__ import annotations

from pytest_bdd import when

from foundry_cli.engine.agent.dispatch import ensure_shape_record_request
from tests.acceptance.acceptance_agent_steps import (
    invoke_agent_submit,
    invoke_visit_lifecycle_complete,
    set_agent_wait_without_submit,
)
from tests.acceptance.acceptance_shape_judgments import acceptance_record_result


@when("I prepare shape record agent wait without auto submit")
def prepare_shape_record_agent_wait(acceptance) -> None:
    set_agent_wait_without_submit(
        acceptance,
        ensure_request=ensure_shape_record_request,
        summary="Shape record judgment required",
    )


@when("I submit record result with PROCEED verdict")
def submit_record_proceed(acceptance) -> None:
    invoke_agent_submit(acceptance, acceptance_record_result("PROCEED"))


@when("I submit record result with BLOCKED verdict")
def submit_record_blocked(acceptance) -> None:
    invoke_agent_submit(acceptance, acceptance_record_result("BLOCKED"))


@when('I invoke "visit record complete" with json output')
def invoke_visit_record_complete(acceptance) -> None:
    invoke_visit_lifecycle_complete(acceptance, "visit record complete")
