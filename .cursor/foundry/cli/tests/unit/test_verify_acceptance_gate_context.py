"""Unit tests for verify.acceptance.gate steward context."""

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


def test_verify_acceptance_gate_context_includes_findings_receipt_and_decider(
    tmp_path: Path,
) -> None:
    acceptance_visit_id = "v-acc-gate-ctx"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    art_dir = run_dir / "artifacts" / acceptance_visit_id
    art_dir.mkdir(parents=True, exist_ok=True)
    findings = {
        "schema_version": "1.0.0",
        "gate_decision": "replan",
        "evidence_ok": False,
        "verdict": "replan",
        "items": [],
    }
    (art_dir / "verify-findings.json").write_text(json.dumps(findings), encoding="utf-8")

    receipt_uri = seal_receipt_path(AGENT_RECEIPT_SCHEMA, acceptance_visit_id)
    receipt_path = resolve_run_uri(receipt_uri, run_dir, acceptance_visit_id)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "2.2.0",
        "receipt_id": "00000000-0000-4000-8000-000000000031",
        "run_id": "00000000-0000-4000-8000-000000000099",
        "timestamp": "2026-01-01T00:00:00Z",
        "step_id": "verify.acceptance",
        "status": "completed",
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    snapshot = {
        "run_id": "00000000-0000-4000-8000-000000000099",
        "ledger": [
            {
                "seq": 1,
                "type": "visit.sealed",
                "visit_id": acceptance_visit_id,
                "node_id": "verify.acceptance",
                "payload": {"outcome": "completed"},
            },
            {
                "seq": 2,
                "type": "artifact.linked",
                "visit_id": acceptance_visit_id,
                "payload": {
                    "artifact_id": "verify-findings",
                    "uri": f"run:artifacts/{acceptance_visit_id}/verify-findings.json",
                },
            },
            {
                "seq": 3,
                "type": "receipt.linked",
                "visit_id": acceptance_visit_id,
                "payload": {
                    "schema": AGENT_RECEIPT_SCHEMA,
                    "path": receipt_uri,
                    "receipt_id": receipt["receipt_id"],
                },
            },
        ],
    }
    visit = {
        "id": "v-ag-ctx",
        "node_id": "verify.acceptance.gate",
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
    findings_read = (context.get("reads") or {}).get("verify_findings") or {}
    assert findings_read.get("gate_decision") == "replan"
    assert findings_read.get("evidence_ok") is False
    receipt_read = (context.get("reads") or {}).get("acceptance_receipt") or {}
    assert receipt_read.get("status") == "completed"
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Acceptance evidence" in markdown
    assert "verify.acceptance" in markdown
    assert "replan" in markdown
    assert "completed" in markdown
    assert "gate decide" in markdown.lower()
    assert "## Instructions" not in markdown
