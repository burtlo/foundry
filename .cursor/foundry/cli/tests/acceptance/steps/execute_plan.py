"""Step definitions specific to execute_plan.feature."""

from __future__ import annotations

from pytest_bdd import when

from foundry_cli.engine.agent.dispatch import ensure_execute_plan_request
from tests.acceptance.acceptance_agent_steps import (
    invoke_agent_submit,
    invoke_visit_lifecycle_complete,
    set_agent_wait_without_submit,
)
from tests.acceptance.acceptance_flow_helpers import advance_acceptance_run_to_execute_plan
from tests.acceptance.acceptance_shape_judgments import acceptance_execute_plan_result


@when("I prepare execute plan opened visit at execute.plan")
def prepare_execute_plan_opened(acceptance) -> None:
    advance_acceptance_run_to_execute_plan(acceptance)


@when("I prepare execute plan agent wait without auto submit")
def prepare_execute_plan_agent_wait(acceptance) -> None:
    advance_acceptance_run_to_execute_plan(acceptance)
    set_agent_wait_without_submit(
        acceptance,
        ensure_request=ensure_execute_plan_request,
        summary="Execute plan judgment required",
    )


@when("I submit plan result with PROCEED verdict")
def submit_plan_proceed(acceptance) -> None:
    run_id = str(acceptance.get("run_id") or "acceptance-run")
    invoke_agent_submit(acceptance, acceptance_execute_plan_result("PROCEED", run_id))


@when("I submit plan result with BLOCKED verdict")
def submit_plan_blocked(acceptance) -> None:
    run_id = str(acceptance.get("run_id") or "acceptance-run")
    invoke_agent_submit(acceptance, acceptance_execute_plan_result("BLOCKED", run_id))


@when('I invoke "visit plan complete"')
def invoke_visit_plan_complete(acceptance) -> None:
    invoke_visit_lifecycle_complete(acceptance, "visit plan complete")
