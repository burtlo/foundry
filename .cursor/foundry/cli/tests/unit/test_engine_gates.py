"""Unit tests for engine gate resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.engine.gates import decide_gate, resolve_engine_gate_decision
from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.receipt_fixtures import (
    execute_test_agent_receipt_body,
    intake_receipt_body,
    minimal_engine_gate_flow,
    opened_gate_visit,
    prepare_run_dir,
    snapshot_with_execute_commit_receipt,
    snapshot_with_execute_test_receipt,
    snapshot_with_sealed_receipt,
)


def test_execute_intake_gate_maps_passed_intake_receipt(tmp_path: Path) -> None:
    intake_visit_id = "v-ei-2"
    run_dir = prepare_run_dir(tmp_path)
    receipt = intake_receipt_body(
        "execute.intake",
        receipt_id="00000000-0000-4000-8000-000000000011",
        checks=[{"id": "validate-manifest", "status": "pass"}],
    )
    snapshot = snapshot_with_sealed_receipt(
        run_dir,
        visit_id=intake_visit_id,
        step_node_id="execute.intake",
        schema=INTAKE_RECEIPT_SCHEMA,
        receipt=receipt,
    )
    visit = opened_gate_visit("v-g2", "execute.intake.gate")
    flow = minimal_engine_gate_flow("execute.intake.gate", ["pass"])
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    assert result["ok"] is True
    assert result["decision"] == "pass"


def test_execute_intake_gate_rejects_blocked_receipt(tmp_path: Path) -> None:
    intake_visit_id = "v-ei"
    run_dir = prepare_run_dir(tmp_path)
    receipt = intake_receipt_body(
        "execute.intake",
        status="blocked",
        receipt_id="00000000-0000-4000-8000-000000000010",
        checks=[{"id": "validate-manifest", "status": "pass"}],
    )
    snapshot = snapshot_with_sealed_receipt(
        run_dir,
        visit_id=intake_visit_id,
        step_node_id="execute.intake",
        schema=INTAKE_RECEIPT_SCHEMA,
        receipt=receipt,
    )
    visit = opened_gate_visit("v-g", "execute.intake.gate")
    flow = minimal_engine_gate_flow("execute.intake.gate", ["pass"])
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    assert result["ok"] is False
    assert result["code"] == "EVIDENCE_MISSING"


def test_decide_gate_denies_engine_gate(tmp_path: Path) -> None:
    visit = opened_gate_visit("v-030", "execute.test.gate")
    snapshot = {"status": "running", "active_visit": visit, "ledger": [], "visits": [visit]}
    flow = {
        "nodes": [
            {
                "id": "execute.test.gate",
                "kind": "gate",
                "decider": "engine",
                "produces": {"options": ["pass", "repair"]},
            }
        ],
        "connections": [],
    }
    result = decide_gate(
        snapshot,
        visit,
        flow,
        decision="pass",
        workspace=tmp_path,
        foundry_bundle=tmp_path,
        run_dir=tmp_path,
    )
    assert result["ok"] is False
    assert result["code"] == "CAPABILITY_DENIED"


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [(0, "pass"), (1, "repair")],
)
def test_execute_test_gate_maps_receipt_commands(
    tmp_path: Path,
    exit_code: int,
    expected: str,
) -> None:
    snapshot, run_dir = snapshot_with_execute_test_receipt(
        tmp_path,
        execute_test_agent_receipt_body(exit_code=exit_code),
    )
    visit = opened_gate_visit("v-031", "execute.test.gate")
    flow = minimal_engine_gate_flow("execute.test.gate", ["pass", "repair"])
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    assert result["ok"] is True
    assert result["decision"] == expected
    assert result["rule_id"].startswith("execute.test.gate/")


def test_execute_repair_limit_gate_proceeds(tmp_path: Path) -> None:
    _, flow = load_registry(FOUNDRY_ROOT)
    snapshot = {"config": {"limits": {"repair": 2}}, "ledger": []}
    visit = opened_gate_visit("v-rl", "execute.repair.limit.gate")
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=tmp_path)
    assert result["ok"] is True
    assert result["decision"] == "proceed"
    assert result["rule_id"] == "execute.repair.limit.gate/proceed"


def test_execute_commit_gate_passes_with_final_sha_and_receipt(tmp_path: Path) -> None:
    snapshot, run_dir = snapshot_with_execute_commit_receipt(tmp_path)
    visit = opened_gate_visit("v-ecg", "execute.commit.gate")
    flow = minimal_engine_gate_flow("execute.commit.gate", ["pass"])
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    assert result["ok"] is True
    assert result["decision"] == "pass"
    assert result["rule_id"] == "execute.commit.gate/final-commit-recorded"
    assert result["evidence_refs"]


@pytest.mark.parametrize(
    "final_commit_sha,include_sealed_visit",
    [
        (None, True),
        ("abc123", False),
    ],
)
def test_execute_commit_gate_rejects_missing_evidence(
    tmp_path: Path,
    final_commit_sha: str | None,
    include_sealed_visit: bool,
) -> None:
    snapshot, run_dir = snapshot_with_execute_commit_receipt(
        tmp_path,
        final_commit_sha=final_commit_sha,
        include_sealed_visit=include_sealed_visit,
    )
    visit = opened_gate_visit("v-ecg-b", "execute.commit.gate")
    flow = minimal_engine_gate_flow("execute.commit.gate", ["pass"])
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    assert result["ok"] is False
    assert result["code"] == "EVIDENCE_MISSING"


def test_execute_repair_limit_gate_exceeds_limit(tmp_path: Path) -> None:
    _, flow = load_registry(FOUNDRY_ROOT)
    snapshot = {
        "config": {"limits": {"repair": 0}},
        "ledger": [
            {
                "seq": 1,
                "type": "connection.taken",
                "payload": {"loop": "repair"},
            }
        ],
    }
    visit = opened_gate_visit("v-rl-over", "execute.repair.limit.gate")
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=tmp_path)
    assert result["ok"] is False
    assert result["code"] == "REPAIR_LIMIT_EXCEEDED"
