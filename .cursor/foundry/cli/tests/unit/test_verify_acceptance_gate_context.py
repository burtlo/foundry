"""Unit tests for verify.acceptance.gate steward context."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import REGISTRY_AGENT_RECEIPT_SCHEMA
from tests.unit.receipt_fixtures import agent_receipt_body, gate_context_arrange


def test_verify_acceptance_gate_context_includes_findings_receipt_and_decider(
    tmp_path: Path,
) -> None:
    acceptance_visit_id = "v-acc-gate-ctx"
    receipt = agent_receipt_body(
        receipt_id="00000000-0000-4000-8000-000000000031",
        step_id="verify.acceptance",
    )
    run_dir, snapshot, visit = gate_context_arrange(
        tmp_path,
        step_visit_id=acceptance_visit_id,
        step_node_id="verify.acceptance",
        gate_visit_id="v-ag-ctx",
        gate_node_id="verify.acceptance.gate",
        schema=REGISTRY_AGENT_RECEIPT_SCHEMA,
        receipt=receipt,
        linked_artifacts=[
            ("verify-findings", f"run:artifacts/{acceptance_visit_id}/verify-findings.json")
        ],
    )
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
