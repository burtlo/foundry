"""Unit tests for execute.commit.gate steward context."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.engine.receipts import seal_receipt_path
from foundry_cli.paths import resolve_run_uri
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT

AGENT_SCHEMA = "registry:schemas/agent-receipt.schema.json"


def test_execute_commit_gate_context_includes_receipt_sha_and_decider(tmp_path: Path) -> None:
    commit_visit_id = "v-ec-ctx"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uri = seal_receipt_path(AGENT_SCHEMA, commit_visit_id)
    path = resolve_run_uri(uri, run_dir, commit_visit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "2.2.0",
        "receipt_id": "00000000-0000-4000-8000-0000000000c1",
        "run_id": "00000000-0000-4000-8000-000000000099",
        "timestamp": "2026-01-01T00:00:00Z",
        "agent": {"name": "commit-agent", "mode": "commit"},
        "status": "completed",
        "provenance": {"source": "test", "run_id": "00000000-0000-4000-8000-000000000099"},
        "recommended_next_state": "execute.commit.gate",
        "commands": [{"command": "git commit", "exit_code": 0}],
    }
    path.write_text(json.dumps(receipt), encoding="utf-8")
    snapshot = {
        "run_id": "00000000-0000-4000-8000-000000000099",
        "state": {
            "final_commit_sha": "abc123def456",
            "execute_commit_message": "feat: ship it",
        },
        "ledger": [
            {
                "seq": 1,
                "type": "visit.sealed",
                "visit_id": commit_visit_id,
                "node_id": "execute.commit",
                "payload": {"outcome": "completed"},
            },
            {
                "seq": 2,
                "type": "receipt.linked",
                "visit_id": commit_visit_id,
                "payload": {
                    "schema": AGENT_SCHEMA,
                    "path": uri,
                    "receipt_id": receipt["receipt_id"],
                },
            },
        ],
    }
    visit = {
        "id": "v-ec-gate",
        "node_id": "execute.commit.gate",
        "kind": "gate",
        "lifecycle": "opened",
    }
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
