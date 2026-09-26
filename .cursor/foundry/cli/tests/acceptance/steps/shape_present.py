"""Step definitions specific to shape_present.feature."""

from __future__ import annotations

from pytest_bdd import when

from tests.acceptance.constants import SCHEMA_VERSION
from tests.acceptance.helpers import active_visit_id, run_dir, write_json


@when("I write present presentation draft to the run directory")
def write_presentation_draft(acceptance) -> None:
    run_dir_path = run_dir(acceptance)
    visit_id = active_visit_id(run_dir_path, default="v-004")
    artifacts_dir = run_dir_path / "artifacts" / visit_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    content = """# Shape plan presentation

## Scope

Implement shape.present CLI commands and engine hooks.

## Acceptance criteria

- User can publish presentation markdown
- Agent receipt seals before transition
"""
    (artifacts_dir / "presentation.md").write_text(content, encoding="utf-8")


@when("I write blocked present agent receipt draft to the run directory")
def write_blocked_present_agent_receipt(acceptance) -> None:
    agent = {
        "schema_version": SCHEMA_VERSION,
        "agent": {"name": "shape-presenter", "mode": "shape"},
        "status": "completed",
        "outputs": {
            "summary_markdown": """# Shape presentation assessment

**Verdict:** BLOCKED

## Presentation draft

Presentation not ready to publish.

## Presented AC

(n/a)

## Verdict summary

Required inputs are missing or acceptance criteria are too vague to present.
""",
        },
        "blockers": ["draft_ac too vague to present"],
    }
    write_json(run_dir(acceptance) / "receipts" / "agent.json", agent)


@when("I write present agent receipt draft to the run directory")
def write_present_agent_receipt(acceptance) -> None:
    run_dir_path = run_dir(acceptance)
    visit_id = active_visit_id(run_dir_path, default="v-004")
    agent = {
        "schema_version": SCHEMA_VERSION,
        "agent": {"name": "shape-presenter", "mode": "shape"},
        "status": "completed",
        "outputs": {
            "summary_markdown": "Presentation ready to publish.",
            "presentation_artifact_path": f"run:artifacts/{visit_id}/presentation.md",
            "presented_ac": "User can publish presentation markdown.",
        },
    }
    write_json(run_dir_path / "receipts" / "agent.json", agent)
