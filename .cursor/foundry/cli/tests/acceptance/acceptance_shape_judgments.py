"""Agent judgment payloads used by shape/execute plan acceptance scenarios."""

from __future__ import annotations

from tests.unit.execute_advance_helpers import stub_execute_plan_result
from tests.unit.shape_flow_helpers import valid_presentation_result, valid_record_result


def acceptance_presentation_result(verdict: str) -> dict:
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


def acceptance_record_result(verdict: str) -> dict:
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


def acceptance_execute_plan_result(verdict: str, run_id: str) -> dict:
    if verdict == "BLOCKED":
        return stub_execute_plan_result(
            run_id,
            summary="BLOCKED: missing sealed plan.",
            verdict="BLOCKED",
            execution_graph={
                "schema_version": "1.0.0",
                "graph_id": "x",
                "work_items": [{"id": "wi", "title": "t"}],
            },
            execute_brief_markdown="n/a",
            blockers=["shape plan missing"],
        )
    return stub_execute_plan_result(
        run_id,
        summary="PROCEED: graph ready.",
        execute_brief_markdown="# Execute brief\n\n## AC\n\nTest AC.\n",
        execution_graph={
            "schema_version": "1.0.0",
            "graph_id": f"{run_id}:execution-graph",
            "run_id": run_id,
            "work_items": [{"id": "wi-001", "title": "Implement AC", "owner": "feature-builder"}],
        },
    )
