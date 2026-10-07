"""Step definitions specific to shape_record.feature."""

from __future__ import annotations

from pytest_bdd import when

from foundry_cli.engine.agent.dispatch import ensure_shape_record_request
from tests.acceptance.acceptance_agent_steps import (
    invoke_agent_submit,
    invoke_visit_lifecycle_complete,
    set_shape_agent_wait_without_submit,
)
from tests.unit.shape_flow_helpers import valid_record_result


def _record_result(verdict: str) -> dict:
    if verdict == "BLOCKED":
        return valid_record_result(
            summary="BLOCKED: presented_ac too vague to freeze.",
            verdict="BLOCKED",
            approved_ac="n/a",
            plan_markdown="n/a",
            blockers=["presented_ac too vague to freeze"],
        )
    return valid_record_result(
        summary="PROCEED: plan ready to publish.",
        approved_ac="User can publish plan markdown.",
        plan_markdown=(
            "# Living plan\n\n"
            "## Scope\n\n"
            "Recorded plan for tests.\n\n"
            "## Acceptance criteria\n\n"
            "User can publish plan markdown.\n"
        ),
    )


@when("I prepare shape record agent wait without auto submit")
def prepare_shape_record_agent_wait(acceptance) -> None:
    set_shape_agent_wait_without_submit(
        acceptance,
        ensure_request=ensure_shape_record_request,
        summary="Shape record judgment required",
    )


@when("I submit record result with PROCEED verdict")
def submit_record_proceed(acceptance) -> None:
    invoke_agent_submit(acceptance, _record_result("PROCEED"))


@when("I submit record result with BLOCKED verdict")
def submit_record_blocked(acceptance) -> None:
    invoke_agent_submit(acceptance, _record_result("BLOCKED"))


@when('I invoke "visit record complete" with json output')
def invoke_visit_record_complete(acceptance) -> None:
    invoke_visit_lifecycle_complete(acceptance, "visit record complete")
