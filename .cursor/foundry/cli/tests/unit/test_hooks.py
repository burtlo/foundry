"""Unit tests for lifecycle hook command checks."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.hooks import run_command_check, run_hook
from tests.unit.constants import REGISTRY_AGENT_RECEIPT_SCHEMA
from tests.unit.receipt_fixtures import (
    agent_receipt_body,
    ledger_receipt_linked,
    ledger_visit_sealed,
    prepare_run_dir,
    write_receipt_to_run,
)


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
    run_dir = prepare_run_dir(tmp_path)
    receipt = agent_receipt_body(
        receipt_id="00000000-0000-4000-8000-000000000001",
        agent={"name": "feature-builder", "mode": "build"},
        recommended_next_state="execute.test",
        commands=[{"command": "dotnet build", "exit_code": 0}],
    )
    uri = write_receipt_to_run(run_dir, visit_id, REGISTRY_AGENT_RECEIPT_SCHEMA, receipt)
    snapshot = {
        "ledger": [
            ledger_visit_sealed("execute.build", visit_id=visit_id, seq=1),
            ledger_receipt_linked(
                visit_id,
                schema=REGISTRY_AGENT_RECEIPT_SCHEMA,
                path=uri,
                receipt_id=str(receipt["receipt_id"]),
                seq=2,
            ),
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
