"""Unit tests for execute.intake.gate steward context."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
from foundry_cli.engine.receipts import seal_receipt_path
from foundry_cli.paths import resolve_run_uri
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT


def test_execute_intake_gate_context_includes_receipt_and_decider(tmp_path: Path) -> None:
    intake_visit_id = "v-ei-ctx"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uri = seal_receipt_path(INTAKE_RECEIPT_SCHEMA, intake_visit_id)
    path = resolve_run_uri(uri, run_dir, intake_visit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "2.2.0",
        "receipt_id": "00000000-0000-4000-8000-000000000020",
        "run_id": "00000000-0000-4000-8000-000000000099",
        "timestamp": "2026-01-01T00:00:00Z",
        "step_id": "execute.intake",
        "status": "passed",
    }
    path.write_text(json.dumps(receipt), encoding="utf-8")
    snapshot = {
        "run_id": "00000000-0000-4000-8000-000000000099",
        "state": {"intake_path": "shaped"},
        "ledger": [
            {
                "seq": 1,
                "type": "visit.sealed",
                "visit_id": intake_visit_id,
                "node_id": "execute.intake",
                "payload": {"outcome": "completed"},
            },
            {
                "seq": 2,
                "type": "receipt.linked",
                "visit_id": intake_visit_id,
                "payload": {
                    "schema": INTAKE_RECEIPT_SCHEMA,
                    "path": uri,
                    "receipt_id": receipt["receipt_id"],
                },
            },
        ],
    }
    visit = {
        "id": "v-g-ctx",
        "node_id": "execute.intake.gate",
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
    intake_read = (context.get("reads") or {}).get("intake_receipt") or {}
    assert intake_read.get("status") == "passed"
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Intake evidence" in markdown
    assert "passed" in markdown
    assert "gate decide" in markdown.lower()
