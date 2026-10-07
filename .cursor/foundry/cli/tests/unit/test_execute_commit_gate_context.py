"""Unit tests for execute.commit.gate steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import REGISTRY_AGENT_RECEIPT_SCHEMA
from tests.unit.receipt_fixtures import agent_receipt_body, gate_context_arrange


def test_execute_commit_gate_context_includes_receipt_sha_and_decider(tmp_path: Path) -> None:
    commit_visit_id = "v-ec-ctx"
    receipt = agent_receipt_body(
        receipt_id="00000000-0000-4000-8000-0000000000c1",
        agent={"name": "commit-agent", "mode": "commit"},
        recommended_next_state="execute.commit.gate",
        commands=[{"command": "git commit", "exit_code": 0}],
    )
    run_dir, snapshot, visit = gate_context_arrange(
        tmp_path,
        step_visit_id=commit_visit_id,
        step_node_id="execute.commit",
        gate_visit_id="v-ec-gate",
        gate_node_id="execute.commit.gate",
        schema=REGISTRY_AGENT_RECEIPT_SCHEMA,
        receipt=receipt,
        state={
            "final_commit_sha": "abc123def456",
            "execute_commit_message": "feat: ship it",
        },
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
    assert (context.get("produces") or {}).get("options") == ["pass"]
    assert "instructions" not in context
    reads = context.get("reads") or {}
    assert (reads.get("state") or {}).get("final_commit_sha") == "abc123def456"
    commit_rec = reads.get("commit_receipt") or {}
    assert commit_rec.get("visit_id") == commit_visit_id
    assert commit_rec.get("status") == "completed"
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Commit evidence" in markdown
    assert "`abc123def456`" in markdown
    assert "run advance" in markdown
    assert "gate decide" in markdown.lower()
    assert "## Instructions" not in markdown
