"""Step definitions specific to shape_record.feature."""

from __future__ import annotations

from pytest_bdd import when

from tests.acceptance.constants import SCHEMA_VERSION
from tests.acceptance.helpers import active_visit_id, run_dir, write_json


@when("I write record plan draft to the run directory")
def write_record_plan_draft(acceptance) -> None:
    run_dir_path = run_dir(acceptance)
    visit_id = active_visit_id(run_dir_path, default="v-006")
    artifacts_dir = run_dir_path / "artifacts" / visit_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    content = """# Living plan

## Scope

Implement shape.record CLI commands and engine hooks.

## Acceptance criteria

- User can publish plan markdown
- Agent receipt seals before transition
- approved_ac_version is recorded before seal
"""
    (artifacts_dir / "plan.md").write_text(content, encoding="utf-8")


@when("I write blocked record agent receipt draft to the run directory")
def write_blocked_record_agent_receipt(acceptance) -> None:
    run_dir_path = run_dir(acceptance)
    visit_id = active_visit_id(run_dir_path, default="v-006")
    assessment_dir = run_dir_path / "receipts" / visit_id
    assessment_dir.mkdir(parents=True, exist_ok=True)
    assessment = """# Shape record assessment

**Verdict:** BLOCKED

## Approved AC

(n/a)

## Plan draft

Plan not ready to publish.

## Verdict summary

Required inputs are missing or acceptance criteria are too vague to freeze.
"""
    (assessment_dir / "assessment.md").write_text(assessment, encoding="utf-8")
    agent = {
        "schema_version": SCHEMA_VERSION,
        "agent": {"name": "shape-recorder", "mode": "shape"},
        "status": "completed",
        "outputs": {
            "assessment_path": f"run:receipts/{visit_id}/assessment.md",
            "summary_markdown": "BLOCKED: presented_ac too vague to freeze.",
        },
        "blockers": ["presented_ac too vague to freeze"],
    }
    write_json(run_dir(acceptance) / "receipts" / "agent.json", agent)


@when("I write record agent receipt draft to the run directory")
def write_record_agent_receipt(acceptance) -> None:
    run_dir_path = run_dir(acceptance)
    visit_id = active_visit_id(run_dir_path, default="v-006")
    assessment_dir = run_dir_path / "receipts" / visit_id
    assessment_dir.mkdir(parents=True, exist_ok=True)
    assessment = """# Shape record assessment

**Verdict:** PROCEED

## Approved AC

User can publish plan markdown.

## Plan draft

# Living plan

## Scope

Implement shape.record CLI commands and engine hooks.

## Verdict summary

Plan ready to publish.
"""
    (assessment_dir / "assessment.md").write_text(assessment, encoding="utf-8")
    agent = {
        "schema_version": SCHEMA_VERSION,
        "agent": {"name": "shape-recorder", "mode": "shape"},
        "status": "completed",
        "outputs": {
            "assessment_path": f"run:receipts/{visit_id}/assessment.md",
            "summary_markdown": "PROCEED: plan ready to publish.",
            "approved_ac": "User can publish plan markdown.",
            "approved_ac_digest": "sha256:abc123",
            "plan_path": f"run:artifacts/{visit_id}/plan.md",
            "plan_version": 1,
        },
    }
    write_json(run_dir_path / "receipts" / "agent.json", agent)
