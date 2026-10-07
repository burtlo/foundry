"""Step definitions specific to shape_intake.feature."""

from __future__ import annotations

from pytest_bdd import parsers, then, when

from tests.acceptance.acceptance_intake_drafts import (
    write_blocked_intake_receipt_drafts,
    write_proceed_intake_receipt_drafts,
    write_ticket_draft,
)
from tests.acceptance.acceptance_invoke import invoke_acceptance_command
from tests.acceptance.helpers import run_dir


@when(parsers.parse('I invoke visit intake complete with work prompt "{prompt}"'))
def invoke_intake_complete_with_prompt(acceptance, prompt: str) -> None:
    invoke_acceptance_command(
        acceptance,
        "visit intake complete",
        extra_flags=["--work-prompt", prompt],
    )


@then("I write ticket draft to the run directory")
def write_ticket_draft_step(acceptance) -> None:
    write_ticket_draft(run_dir(acceptance))


@then("I write receipt drafts to the run directory")
def write_receipt_drafts(acceptance) -> None:
    write_proceed_intake_receipt_drafts(run_dir(acceptance))


@then("I write blocked receipt drafts to the run directory")
def write_blocked_receipt_drafts(acceptance) -> None:
    write_blocked_intake_receipt_drafts(run_dir(acceptance))
