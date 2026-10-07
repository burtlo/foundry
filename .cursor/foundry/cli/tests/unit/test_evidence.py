"""Unit tests for engine evidence read model."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.evidence import (
    AGENT_RECEIPT_SCHEMA,
    INTAKE_RECEIPT_SCHEMA,
    agent_receipt_summary,
    intake_receipt_summary,
    load_linked_receipt,
    sealed_step_visit_id,
)
from tests.unit.receipt_fixtures import (
    agent_receipt_body,
    intake_receipt_body,
    ledger_receipt_linked,
    ledger_visit_sealed,
    prepare_run_dir,
    write_receipt_to_run,
)


def test_sealed_step_visit_id_returns_latest_sealed(tmp_path: Path) -> None:
    snapshot = {
        "ledger": [
            ledger_visit_sealed("execute.test", visit_id="v-old", seq=1),
            ledger_visit_sealed("execute.test", visit_id="v-new", seq=2),
        ]
    }
    assert sealed_step_visit_id(snapshot, "execute.test") == "v-new"
    assert sealed_step_visit_id(snapshot, "execute.build") is None


def test_load_linked_receipt_reads_agent_file(tmp_path: Path) -> None:
    visit_id = "v-001"
    run_dir = prepare_run_dir(tmp_path)
    receipt = agent_receipt_body(
        receipt_id="00000000-0000-4000-8000-000000000001",
        agent={"name": "t", "mode": "test"},
        recommended_next_state="execute.test.gate",
        commands=[{"command": "pytest", "exit_code": 0}],
    )
    uri = write_receipt_to_run(run_dir, visit_id, AGENT_RECEIPT_SCHEMA, receipt)
    snapshot = {
        "ledger": [
            ledger_receipt_linked(
                visit_id,
                schema=AGENT_RECEIPT_SCHEMA,
                path=uri,
                receipt_id=str(receipt["receipt_id"]),
            ),
        ]
    }
    loaded = load_linked_receipt(snapshot, visit_id, AGENT_RECEIPT_SCHEMA, run_dir)
    assert loaded is not None
    assert loaded.get("receipt_id") == receipt["receipt_id"]
    assert loaded.get("_missing_file") is None


def test_load_linked_receipt_missing_file_marker(tmp_path: Path) -> None:
    visit_id = "v-002"
    run_dir = prepare_run_dir(tmp_path)
    snapshot = {
        "ledger": [
            ledger_receipt_linked(
                visit_id,
                schema=AGENT_RECEIPT_SCHEMA,
                path="run:receipts/v-002/missing.json",
                receipt_id="rid",
            ),
        ]
    }
    loaded = load_linked_receipt(snapshot, visit_id, AGENT_RECEIPT_SCHEMA, run_dir)
    assert loaded is not None
    assert "_missing_file" in loaded


def test_intake_receipt_summary_for_sealed_step(tmp_path: Path) -> None:
    visit_id = "v-intake"
    run_dir = prepare_run_dir(tmp_path)
    receipt = intake_receipt_body(
        "execute.intake",
        status="passed",
        receipt_id="00000000-0000-4000-8000-000000000002",
    )
    uri = write_receipt_to_run(run_dir, visit_id, INTAKE_RECEIPT_SCHEMA, receipt)
    snapshot = {
        "ledger": [
            ledger_visit_sealed("execute.intake", visit_id=visit_id, seq=1),
            ledger_receipt_linked(
                visit_id,
                schema=INTAKE_RECEIPT_SCHEMA,
                path=uri,
                receipt_id=str(receipt["receipt_id"]),
                seq=2,
            ),
        ]
    }
    summary = intake_receipt_summary(snapshot, run_dir=run_dir, step_node_id="execute.intake")
    assert summary is not None
    assert summary["visit_id"] == visit_id
    assert summary["status"] == "passed"
    assert summary["receipt_id"] == str(receipt["receipt_id"])
    assert summary["resolved_path"] is not None


def test_agent_receipt_summary_includes_commands(tmp_path: Path) -> None:
    visit_id = "v-test"
    run_dir = prepare_run_dir(tmp_path)
    receipt = agent_receipt_body(
        receipt_id="00000000-0000-4000-8000-000000000003",
        agent={"name": "t", "mode": "test"},
        recommended_next_state="execute.test.gate",
        commands=[{"command": "make test", "exit_code": 1}],
    )
    uri = write_receipt_to_run(run_dir, visit_id, AGENT_RECEIPT_SCHEMA, receipt)
    snapshot = {
        "ledger": [
            ledger_visit_sealed("execute.test", visit_id=visit_id, seq=1),
            ledger_receipt_linked(
                visit_id,
                schema=AGENT_RECEIPT_SCHEMA,
                path=uri,
                receipt_id=str(receipt["receipt_id"]),
                seq=2,
            ),
        ]
    }
    summary = agent_receipt_summary(snapshot, run_dir=run_dir, step_node_id="execute.test")
    assert summary is not None
    assert summary["commands"] == [{"command": "make test", "exit_code": 1}]
    assert summary["status"] == str(receipt.get("status") or "")
