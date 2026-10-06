"""Unit tests for verify.code_quality.gate steward context."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.engine.hooks import AGENT_RECEIPT_SCHEMA
from foundry_cli.engine.receipts import seal_receipt_path
from foundry_cli.paths import resolve_run_uri
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT


def test_verify_code_quality_gate_context_includes_receipt_and_decider(tmp_path: Path) -> None:
    quality_visit_id = "v-cq-gate-ctx"
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    receipt_uri = seal_receipt_path(AGENT_RECEIPT_SCHEMA, quality_visit_id)
    receipt_path = resolve_run_uri(receipt_uri, run_dir, quality_visit_id)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "2.2.0",
        "receipt_id": "00000000-0000-4000-8000-000000000041",
        "run_id": "00000000-0000-4000-8000-000000000099",
        "timestamp": "2026-01-01T00:00:00Z",
        "step_id": "verify.code_quality",
        "status": "completed",
        "commands": [
            {"command": "npm run lint", "exit_code": 1},
        ],
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    snapshot = {
        "run_id": "00000000-0000-4000-8000-000000000099",
        "ledger": [
            {
                "seq": 1,
                "type": "visit.sealed",
                "visit_id": quality_visit_id,
                "node_id": "verify.code_quality",
                "payload": {"outcome": "completed"},
            },
            {
                "seq": 2,
                "type": "receipt.linked",
                "visit_id": quality_visit_id,
                "payload": {
                    "schema": AGENT_RECEIPT_SCHEMA,
                    "path": receipt_uri,
                    "receipt_id": receipt["receipt_id"],
                },
            },
        ],
    }
    visit = {
        "id": "v-cqg-ctx",
        "node_id": "verify.code_quality.gate",
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
