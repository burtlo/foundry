"""Unit tests for execute.repair.limit.gate steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.render import render_context_markdown
from tests.unit.constants import TEST_RUN_UUID
from tests.unit.context_test_helpers import assemble_step_context


def test_execute_repair_limit_gate_context_includes_loop_and_decider(tmp_path: Path) -> None:
    snapshot = {
        "run_id": TEST_RUN_UUID,
        "config": {"limits": {"repair": 2}},
        "ledger": [
            {
                "seq": 1,
                "type": "connection.taken",
                "payload": {"loop": "repair", "connection_id": "a"},
            }
        ],
    }
    visit = {
        "id": "v-rl-ctx",
        "node_id": "execute.repair.limit.gate",
        "kind": "gate",
        "lifecycle": "opened",
    }
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    context = assemble_step_context(run_dir, snapshot, visit)
    assert context.get("decider") == "engine"
    assert (context.get("produces") or {}).get("options") == ["proceed"]
    loop = (context.get("reads") or {}).get("repair_loop") or {}
    assert loop == {"repair_count": 1, "limit": 2, "within_limit": True}
    assert "instructions" not in context
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Repair loop" in markdown
    assert "**1** of limit **2**" in markdown
    assert "run advance" in markdown
    assert "gate decide" in markdown.lower()
    assert "## Instructions" not in markdown
