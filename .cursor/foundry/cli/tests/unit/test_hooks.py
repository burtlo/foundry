"""Unit tests for lifecycle hook command checks."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.hooks import run_command_check, run_hook
from tests.unit.constants import REGISTRY_AGENT_RECEIPT_SCHEMA
from tests.unit.git_workspace import init_clean_git_repo
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


def test_validate_verify_context_requires_snapshot() -> None:
    result = run_command_check(
        "validate-verify-context",
        {"command": "validate_verify_context"},
        workspace=Path("."),
        foundry_bundle=Path("."),
        snapshot=None,
    )
    assert result["result"] == "fail"
    assert result["detail"]["reason"] == "snapshot_required"


def test_validate_git_clean_execute_passes_clean_repo(tmp_path: Path) -> None:
    init_clean_git_repo(tmp_path)
    result = run_command_check(
        "validate-git-clean-execute",
        {"command": "validate_git_clean_execute"},
        workspace=tmp_path,
        foundry_bundle=tmp_path,
    )
    assert result["result"] == "pass"


def test_validate_git_clean_execute_fails_dirty_worktree(tmp_path: Path) -> None:
    init_clean_git_repo(tmp_path)
    (tmp_path / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    result = run_command_check(
        "validate-git-clean-execute",
        {"command": "validate_git_clean_execute"},
        workspace=tmp_path,
        foundry_bundle=tmp_path,
    )
    assert result["result"] == "fail"
    assert result["detail"]["reason"] == "dirty_worktree"


def test_validate_git_clean_execute_fails_without_git_repo(tmp_path: Path) -> None:
    result = run_command_check(
        "validate-git-clean-execute",
        {"command": "validate_git_clean_execute"},
        workspace=tmp_path,
        foundry_bundle=tmp_path,
    )
    assert result["result"] == "fail"
    assert result["detail"]["reason"] == "git_status_failed"


def test_ensure_execution_graph_reference_pass_and_fail() -> None:
    passing = run_command_check(
        "ensure-execution-graph-reference",
        {"command": "ensure_execution_graph_reference"},
        workspace=Path("."),
        foundry_bundle=Path("."),
        snapshot={"state": {"execution_graph_id": "graph-42"}},
    )
    assert passing["result"] == "pass"

    missing_snapshot = run_command_check(
        "ensure-execution-graph-reference",
        {"command": "ensure_execution_graph_reference"},
        workspace=Path("."),
        foundry_bundle=Path("."),
        snapshot=None,
    )
    assert missing_snapshot["result"] == "fail"
    assert missing_snapshot["detail"]["reason"] == "snapshot_required"

    missing_id = run_command_check(
        "ensure-execution-graph-reference",
        {"command": "ensure_execution_graph_reference"},
        workspace=Path("."),
        foundry_bundle=Path("."),
        snapshot={"state": {}},
    )
    assert missing_id["result"] == "fail"
    assert missing_id["detail"]["reason"] == "execution_graph_id_missing"


def test_validate_build_exit_fails_without_prerequisites(tmp_path: Path) -> None:
    run_dir = prepare_run_dir(tmp_path)
    missing_inputs = run_command_check(
        "validate-build-exit",
        {"command": "validate_build_exit"},
        workspace=tmp_path,
        foundry_bundle=tmp_path,
        snapshot=None,
        run_dir=None,
    )
    assert missing_inputs["result"] == "fail"
    assert missing_inputs["detail"]["reason"] == "snapshot_and_run_dir_required"

    no_build = run_command_check(
        "validate-build-exit",
        {"command": "validate_build_exit"},
        workspace=tmp_path,
        foundry_bundle=tmp_path,
        snapshot={"ledger": [], "state": {}},
        run_dir=run_dir,
    )
    assert no_build["result"] == "fail"
    assert no_build["detail"]["reason"] == "execute.build_not_sealed"


def test_validate_build_exit_fails_on_nonzero_command(tmp_path: Path) -> None:
    visit_id = "v-011"
    run_dir = prepare_run_dir(tmp_path)
    receipt = agent_receipt_body(
        receipt_id="00000000-0000-4000-8000-000000000002",
        agent={"name": "feature-builder", "mode": "build"},
        recommended_next_state="execute.test",
        commands=[{"command": "dotnet build", "exit_code": 1}],
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
    assert result["result"] == "fail"
    assert result["detail"]["reason"] == "build_command_failed"


def test_run_hook_non_command_check_without_evaluator_fails(tmp_path: Path) -> None:
    flow = {
        "checks": {"receipt-only": {"schema": "registry:schemas/agent-receipt.schema.json"}},
        "nodes": [
            {
                "id": "demo",
                "kind": "step",
                "lifecycle": {"on_open": [{"check": "receipt-only", "on_fail": {"action": "halt"}}]},
            }
        ],
    }
    visit = {"id": "v-002", "node_id": "demo", "lifecycle": "opened"}
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
    assert result["check_id"] == "receipt-only"
    recorded = [e for e in snapshot["ledger"] if e.get("type") == "check.recorded"]
    assert recorded[-1]["payload"]["result"] == "fail"
    assert recorded[-1]["payload"]["detail"]["reason"] == "no_evaluator"


def test_run_hook_when_expression_check_evaluates_history(tmp_path: Path) -> None:
    flow = {
        "checks": {
            "prior-build": {
                "when": "history.last('visit.sealed', node_id='execute.build') != null",
            }
        },
        "nodes": [
            {
                "id": "demo",
                "kind": "step",
                "lifecycle": {"on_open": [{"check": "prior-build"}]},
            }
        ],
    }
    visit = {"id": "v-003", "node_id": "demo", "lifecycle": "opened"}
    snapshot = {
        "ledger": [ledger_visit_sealed("execute.build", visit_id="v-build", seq=1)],
        "state": {},
    }
    result = run_hook(
        snapshot,
        visit,
        flow,
        "on_open",
        workspace=tmp_path,
        foundry_bundle=tmp_path,
        run_dir=tmp_path,
    )
    assert result["ok"] is True
