"""On-disk intake receipt drafts for shape.intake acceptance scenarios."""

from __future__ import annotations

from pathlib import Path

from tests.acceptance.constants import SCHEMA_VERSION
from tests.acceptance.helpers import write_json


def write_ticket_draft(run_dir: Path) -> None:
    ticket = {
        "schema_version": SCHEMA_VERSION,
        "raw_input": "Add shape intake vertical slice",
        "normalized_translation": "Implement shape.intake CLI commands and engine hooks.",
        "source_type": "chat",
        "source_ref": None,
        "issue_key": None,
    }
    write_json(run_dir / "ticket.json", ticket)


def write_proceed_intake_receipt_drafts(run_dir: Path) -> None:
    receipts_dir = run_dir / "receipts"
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


def write_blocked_intake_receipt_drafts(run_dir: Path) -> None:
    receipts_dir = run_dir / "receipts"
    assessment = """# Shape intake assessment

**Verdict:** BLOCKED

## Findings

- Manifest issue blocks intake.

## Ticket draft

| Field | Proposed value |
|-------|----------------|
| raw_input | blocked request |
| normalized_translation | n/a |
| source_type | chat |
| source_ref | null |
| issue_key | null |

## Verdict summary

Blocked until manifest is fixed.
"""
    (receipts_dir / "assessment.md").write_text(assessment, encoding="utf-8")
    intake = {
        "schema_version": SCHEMA_VERSION,
        "step_id": "shape.intake",
        "status": "blocked",
        "checks": [{"id": "validate-manifest", "status": "pass", "summary": "Manifest valid"}],
        "agent_assessment": {
            "assessment_path": "run:receipts/assessment.md",
            "summary_markdown": "BLOCKED: fix manifest.",
            "blocked_reason": "example",
        },
    }
    agent = {
        "schema_version": SCHEMA_VERSION,
        "agent": {"name": "intake-checker.shape", "mode": "shape"},
        "status": "completed",
        "outputs": {
            "assessment_path": "run:receipts/assessment.md",
            "summary_markdown": "BLOCKED: fix manifest.",
        },
    }
    write_json(receipts_dir / "intake.json", intake)
    write_json(receipts_dir / "agent.json", agent)
