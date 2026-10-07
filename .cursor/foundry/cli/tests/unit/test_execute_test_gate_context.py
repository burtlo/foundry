"""Unit tests for execute.test.gate steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import REGISTRY_AGENT_RECEIPT_SCHEMA
from tests.unit.receipt_fixtures import agent_receipt_body, gate_context_arrange


def test_execute_test_gate_context_includes_receipt_and_decider(tmp_path: Path) -> None:
    receipt = agent_receipt_body(
        receipt_id="00000000-0000-4000-8000-000000000021",
        agent={"name": "repairer", "mode": "repair"},
        commands=[{"command": "pytest", "exit_code": 0}],
    )
    run_dir, snapshot, visit = gate_context_arrange(
        tmp_path,
        step_visit_id="v-et-ctx",
        step_node_id="execute.test",
        gate_visit_id="v-tg-ctx",
        gate_node_id="execute.test.gate",
        schema=REGISTRY_AGENT_RECEIPT_SCHEMA,
        receipt=receipt,
        state={"last_test_exit_code": 0},
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
    test_read = (context.get("reads") or {}).get("test_receipt") or {}
    assert test_read.get("commands") == [{"command": "pytest", "exit_code": 0}]
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Test evidence" in markdown
    assert "exit 0" in markdown
    assert "gate decide" in markdown.lower()
