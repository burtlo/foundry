"""Unit tests for lifecycle hook command checks."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.engine.hooks import run_command_check, run_hook
from foundry_cli.engine.receipts import seal_receipt_path

AGENT_SCHEMA = "registry:schemas/agent-receipt.schema.json"


def test_run_command_check_unknown_command_fails() -> None:
    result = run_command_check(
        "unknown",
        {"command": "not_a_real_command"},
        workspace=Path("."),
        foundry_bundle=Path("."),
    )
    assert result["result"] == "fail"
    assert result["detail"]["reason"] == "unknown_command"


def test_run_hook_unknown_check_id_fails_closed(tmp_path: Path) -> None:
    flow = {
        "checks": {},
        "nodes": [
            {
                "id": "demo",
                "kind": "step",
                "lifecycle": {"on_open": [{"check": "missing-check", "on_fail": {"action": "halt"}}]},
            }
        ],
    }
    visit = {"id": "v-001", "node_id": "demo", "lifecycle": "opened"}
    snapshot = {"ledger": [], "state": {}}
    result = run_hook(
        snapshot,
        visit,
        flow,
        "on_open",
        workspace=tmp_path,
        foundry_bundle=tmp_path,
        run_dir=tmp_path,
    )
    assert result["ok"] is False
    assert result["check_id"] == "missing-check"


def test_validate_build_exit_reads_linked_receipt(tmp_path: Path) -> None:
    visit_id = "v-010"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    receipt = {
        "schema_version": "2.2.0",
        "receipt_id": "00000000-0000-4000-8000-000000000001",
        "run_id": "00000000-0000-4000-8000-000000000099",
        "timestamp": "2026-01-01T00:00:00Z",
        "agent": {"name": "feature-builder", "mode": "build"},
        "status": "completed",
        "provenance": {"source": "test", "run_id": "00000000-0000-4000-8000-000000000099"},
        "recommended_next_state": "execute.test",
        "commands": [{"command": "dotnet build", "exit_code": 0}],
    }
    uri = seal_receipt_path(AGENT_SCHEMA, visit_id)
    from foundry_cli.paths import resolve_run_uri

    path = resolve_run_uri(uri, run_dir, visit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt), encoding="utf-8")

    snapshot = {
        "ledger": [
            {
                "seq": 1,
                "type": "visit.sealed",
                "visit_id": visit_id,
                "node_id": "execute.build",
                "payload": {"outcome": "completed"},
            },
            {
                "seq": 2,
                "type": "receipt.linked",
                "visit_id": visit_id,
                "payload": {"schema": AGENT_SCHEMA, "path": uri, "receipt_id": receipt["receipt_id"]},
            },
        ]
    }
    result = run_command_check(
        "validate-build-exit",
        {"command": "validate_build_exit"},
        workspace=tmp_path,
        foundry_bundle=tmp_path,
        snapshot=snapshot,
        run_dir=run_dir,
    )
    assert result["result"] == "pass"


def test_validate_verify_context_requires_state_keys() -> None:
    fail = run_command_check(
        "validate-verify-context",
        {"command": "validate_verify_context"},
        workspace=Path("."),
        foundry_bundle=Path("."),
        snapshot={"state": {"feature_branch": "feat/x"}},
    )
    assert fail["result"] == "fail"

    pass_result = run_command_check(
        "validate-verify-context",
        {"command": "validate_verify_context"},
        workspace=Path("."),
        foundry_bundle=Path("."),
        snapshot={
            "state": {
                "feature_branch": "feat/x",
                "default_branch": "main",
                "final_commit_sha": "abc",
                "execution_graph_id": "graph-1",
            }
        },
    )
    assert pass_result["result"] == "pass"
