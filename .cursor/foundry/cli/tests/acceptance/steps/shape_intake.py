"""Step definitions specific to shape_intake.feature."""

from __future__ import annotations

from pytest_bdd import then

from tests.acceptance.constants import SCHEMA_VERSION
from tests.acceptance.helpers import run_dir, write_json


@then("I write ticket draft to the run directory")
def write_ticket_draft(acceptance) -> None:
    ticket = {
        "schema_version": SCHEMA_VERSION,
        "raw_input": "Add shape intake vertical slice",
        "normalized_translation": "Implement shape.intake CLI commands and engine hooks.",
        "source_type": "chat",
        "source_ref": None,
        "issue_key": None,
    }
    write_json(run_dir(acceptance) / "ticket.json", ticket)


@then("I write receipt drafts to the run directory")
def write_receipt_drafts(acceptance) -> None:
    receipts_dir = run_dir(acceptance) / "receipts"
    assessment = """# Shape intake assessment

**Verdict:** PROCEED

## Findings

- Work request present.

## Ticket draft

| Field | Proposed value |
|-------|----------------|
| raw_input | Add shape intake vertical slice |
| normalized_translation | Implement shape.intake CLI commands and engine hooks. |
| source_type | chat |
| source_ref | null |
| issue_key | null |

## Verdict summary

Shape intake can proceed.
"""
    (receipts_dir / "assessment.md").write_text(assessment, encoding="utf-8")
    intake = {
        "schema_version": SCHEMA_VERSION,
        "step_id": "shape.intake",
        "status": "passed",
        "checks": [{"id": "validate-manifest", "status": "pass", "summary": "Manifest valid"}],
        "agent_assessment": {
            "assessment_path": "run:receipts/assessment.md",
            "summary_markdown": "PROCEED: shape intake can proceed.",
        },
    }
    agent = {
        "schema_version": SCHEMA_VERSION,
        "agent": {"name": "intake-checker.shape", "mode": "shape"},
        "status": "completed",
        "recommended_next_state": "shape.examine",
        "outputs": {
            "assessment_path": "run:receipts/assessment.md",
            "summary_markdown": "PROCEED: shape intake can proceed.",
        },
    }
    write_json(receipts_dir / "intake.json", intake)
    write_json(receipts_dir / "agent.json", agent)
