"""Unit tests for verify.code_quality.gate steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import REGISTRY_AGENT_RECEIPT_SCHEMA
from tests.unit.receipt_fixtures import agent_receipt_body, gate_context_arrange


def test_verify_code_quality_gate_context_includes_receipt_and_decider(tmp_path: Path) -> None:
    quality_visit_id = "v-cq-gate-ctx"
    receipt = agent_receipt_body(
        receipt_id="00000000-0000-4000-8000-000000000041",
        step_id="verify.code_quality",
        commands=[{"command": "npm run lint", "exit_code": 1}],
    )
    run_dir, snapshot, visit = gate_context_arrange(
        tmp_path,
        step_visit_id=quality_visit_id,
        step_node_id="verify.code_quality",
        gate_visit_id="v-cqg-ctx",
        gate_node_id="verify.code_quality.gate",
        schema=REGISTRY_AGENT_RECEIPT_SCHEMA,
        receipt=receipt,
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
    assert "instructions" not in context
    receipt_read = (context.get("reads") or {}).get("code_quality_receipt") or {}
    assert receipt_read.get("visit_id") == quality_visit_id
    assert receipt_read.get("status") == "completed"
    commands = receipt_read.get("commands") or []
    assert commands[0].get("exit_code") == 1
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Code quality evidence" in markdown
    assert "verify.code_quality" in markdown
    assert "npm run lint" in markdown
    assert "exit 1" in markdown
    assert "repair" in markdown.lower()
    assert "gate decide" in markdown.lower()
    assert "## Instructions" not in markdown
