"""Unit tests for engine gate resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foundry_cli.engine.gates import decide_gate, resolve_engine_gate_decision
from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
from foundry_cli.engine.receipts import seal_receipt_path
from foundry_cli.paths import resolve_run_uri

AGENT_SCHEMA = "registry:schemas/agent-receipt.schema.json"


def _agent_receipt(*, status: str = "completed", exit_code: int = 0) -> dict:
    return {
        "schema_version": "2.2.0",
        "receipt_id": "00000000-0000-4000-8000-000000000002",
        "run_id": "00000000-0000-4000-8000-000000000099",
        "timestamp": "2026-01-01T00:00:00Z",
        "agent": {"name": "repairer", "mode": "repair"},
        "status": status,
        "provenance": {"source": "test", "run_id": "00000000-0000-4000-8000-000000000099"},
        "recommended_next_state": "execute.test.gate",
        "commands": [{"command": "pytest", "exit_code": exit_code}],
    }


def _snapshot_with_test_receipt(tmp_path: Path, receipt: dict) -> tuple[dict, Path]:
    test_visit_id = "v-020"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uri = seal_receipt_path(AGENT_SCHEMA, test_visit_id)
    path = resolve_run_uri(uri, run_dir, test_visit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt), encoding="utf-8")
    snapshot = {
        "ledger": [
            {
                "seq": 1,
                "type": "visit.sealed",
                "visit_id": test_visit_id,
                "node_id": "execute.test",
                "payload": {"outcome": "completed"},
            },
            {
                "seq": 2,
                "type": "receipt.linked",
                "visit_id": test_visit_id,
                "payload": {
                    "schema": AGENT_SCHEMA,
                    "path": uri,
                    "receipt_id": receipt["receipt_id"],
                },
            },
        ]
    }
    return snapshot, run_dir


def test_execute_intake_gate_maps_passed_intake_receipt(tmp_path: Path) -> None:
    intake_visit_id = "v-ei-2"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uri = seal_receipt_path(INTAKE_RECEIPT_SCHEMA, intake_visit_id)
    path = resolve_run_uri(uri, run_dir, intake_visit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "2.2.0",
        "receipt_id": "00000000-0000-4000-8000-000000000011",
        "run_id": "00000000-0000-4000-8000-000000000099",
        "timestamp": "2026-01-01T00:00:00Z",
        "step_id": "execute.intake",
        "status": "passed",
        "checks": [{"id": "validate-manifest", "status": "pass"}],
    }
    path.write_text(json.dumps(receipt), encoding="utf-8")
    snapshot = {
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
        ]
    }
    visit = {"id": "v-g2", "node_id": "execute.intake.gate", "kind": "gate", "lifecycle": "opened"}
    flow = {
        "nodes": [
            {
                "id": "execute.intake.gate",
                "kind": "gate",
                "decider": "engine",
                "produces": {"options": ["pass"]},
            }
        ]
    }
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    assert result["ok"] is True
    assert result["decision"] == "pass"


def test_decide_gate_denies_engine_gate(tmp_path: Path) -> None:
    visit = {"id": "v-030", "node_id": "execute.test.gate", "kind": "gate", "lifecycle": "opened"}
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
    snapshot, run_dir = _snapshot_with_test_receipt(tmp_path, _agent_receipt(exit_code=exit_code))
    visit = {"id": "v-031", "node_id": "execute.test.gate", "kind": "gate", "lifecycle": "opened"}
    flow = {
        "nodes": [
            {
                "id": "execute.test.gate",
                "kind": "gate",
                "decider": "engine",
                "produces": {"options": ["pass", "repair"]},
            }
        ]
    }
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    assert result["ok"] is True
    assert result["decision"] == expected
    assert result["rule_id"].startswith("execute.test.gate/")


def test_execute_repair_limit_gate_proceeds(tmp_path: Path) -> None:
    from foundry_cli.registry import load_registry
    from tests.conftest import FOUNDRY_ROOT

    _, flow = load_registry(FOUNDRY_ROOT)
    snapshot = {"config": {"limits": {"repair": 2}}, "ledger": []}
    visit = {
        "id": "v-rl",
        "node_id": "execute.repair.limit.gate",
        "kind": "gate",
        "lifecycle": "opened",
    }
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=tmp_path)
    assert result["ok"] is True
    assert result["decision"] == "proceed"
    assert result["rule_id"] == "execute.repair.limit.gate/proceed"


def _snapshot_with_commit_receipt(
    tmp_path: Path,
    *,
    final_commit_sha: str | None = "abc123",
    include_sealed_visit: bool = True,
) -> tuple[dict, Path]:
    commit_visit_id = "v-commit-g"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uri = seal_receipt_path(AGENT_SCHEMA, commit_visit_id)
    path = resolve_run_uri(uri, run_dir, commit_visit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = _agent_receipt(status="completed")
    receipt["agent"] = {"name": "commit-agent", "mode": "commit"}
    receipt["recommended_next_state"] = "execute.commit.gate"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    ledger: list[dict] = []
    if include_sealed_visit:
        ledger.append(
            {
                "seq": 1,
                "type": "visit.sealed",
                "visit_id": commit_visit_id,
                "node_id": "execute.commit",
                "payload": {"outcome": "completed"},
            }
        )
        ledger.append(
            {
                "seq": 2,
                "type": "receipt.linked",
                "visit_id": commit_visit_id,
                "payload": {
                    "schema": AGENT_SCHEMA,
                    "path": uri,
                    "receipt_id": receipt["receipt_id"],
                },
            }
        )
    state: dict = {}
    if final_commit_sha is not None:
        state["final_commit_sha"] = final_commit_sha
    snapshot = {"state": state, "ledger": ledger}
    return snapshot, run_dir


def test_execute_commit_gate_passes_with_final_sha_and_receipt(tmp_path: Path) -> None:
    snapshot, run_dir = _snapshot_with_commit_receipt(tmp_path)
    visit = {"id": "v-ecg", "node_id": "execute.commit.gate", "kind": "gate", "lifecycle": "opened"}
    flow = {
        "nodes": [
            {
                "id": "execute.commit.gate",
                "kind": "gate",
                "decider": "engine",
                "produces": {"options": ["pass"]},
            }
        ]
    }
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
    snapshot, run_dir = _snapshot_with_commit_receipt(
        tmp_path,
        final_commit_sha=final_commit_sha,
        include_sealed_visit=include_sealed_visit,
    )
    visit = {"id": "v-ecg-b", "node_id": "execute.commit.gate", "kind": "gate", "lifecycle": "opened"}
    flow = {
        "nodes": [
            {
                "id": "execute.commit.gate",
                "kind": "gate",
                "decider": "engine",
                "produces": {"options": ["pass"]},
            }
        ]
    }
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    assert result["ok"] is False
    assert result["code"] == "EVIDENCE_MISSING"


def test_execute_repair_limit_gate_exceeds_limit(tmp_path: Path) -> None:
    from foundry_cli.registry import load_registry
    from tests.conftest import FOUNDRY_ROOT

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
    visit = {
        "id": "v-rl-over",
        "node_id": "execute.repair.limit.gate",
        "kind": "gate",
        "lifecycle": "opened",
    }
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=tmp_path)
    assert result["ok"] is False
    assert result["code"] == "REPAIR_LIMIT_EXCEEDED"
