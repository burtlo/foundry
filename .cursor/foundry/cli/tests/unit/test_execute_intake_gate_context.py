"""Unit tests for execute.intake.gate steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.receipt_fixtures import gate_context_arrange, intake_receipt_body


def test_execute_intake_gate_context_includes_receipt_and_decider(tmp_path: Path) -> None:
    receipt = intake_receipt_body(
        "execute.intake",
        receipt_id="00000000-0000-4000-8000-000000000020",
    )
    run_dir, snapshot, visit = gate_context_arrange(
        tmp_path,
        step_visit_id="v-ei-ctx",
        step_node_id="execute.intake",
        gate_visit_id="v-g-ctx",
        gate_node_id="execute.intake.gate",
        schema=INTAKE_RECEIPT_SCHEMA,
        receipt=receipt,
        state={"intake_path": "shaped"},
    )
    _, flow = load_registry(FOUNDRY_ROOT)
    context = assemble_context(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        foundry_bundle=FOUNDRY_ROOT,
        run_dir=run_dir,
    )
    assert context.get("decider") == "engine"
    intake_read = (context.get("reads") or {}).get("intake_receipt") or {}
    assert intake_read.get("status") == "passed"
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Intake evidence" in markdown
    assert "passed" in markdown
    assert "gate decide" in markdown.lower()
