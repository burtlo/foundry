"""Unit tests for execute.repair.limit.gate steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT


def test_execute_repair_limit_gate_context_includes_loop_and_decider(tmp_path: Path) -> None:
    snapshot = {
        "run_id": "00000000-0000-4000-8000-000000000099",
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
    _, flow = load_registry(FOUNDRY_ROOT)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    context = assemble_context(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        foundry_bundle=FOUNDRY_ROOT,
        run_dir=run_dir,
    )
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
