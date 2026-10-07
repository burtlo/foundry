"""Verify evidence hardening — intake, acceptance, code quality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
from foundry_cli.engine.agent.dispatch import ensure_verify_acceptance_request
from foundry_cli.engine.agent.submit import submit_agent_result
from foundry_cli.engine.lifecycle import admit_visit, update_active_visit
from foundry_cli.engine.verify_step_executor import (
    VERIFY_ACCEPTANCE_NODE,
    VERIFY_CODE_QUALITY_NODE,
    VERIFY_CODE_REVIEW_NODE,
    VERIFY_COMPLETE_NODE,
    VERIFY_INTAKE_NODE,
    _assess_acceptance,
    _commands_for_code_quality,
    _resolve_acceptance_decision,
    _validate_verify_intake_context,
    findings_from_acceptance_result,
    run_verify_acceptance_complete,
    run_verify_code_quality_complete,
    run_verify_code_review_complete,
    run_verify_complete_complete,
    run_verify_intake_complete,
)
from tests.unit.execute_advance_helpers import stub_verify_acceptance_result
from tests.unit.git_workspace import init_clean_git_repo
from foundry_cli.registry import load_registry
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import IMPLEMENTATION_FLOW, TEST_RUN_UUID
from tests.unit.receipt_fixtures import (
    intake_receipt_body,
    ledger_artifact_linked,
    ledger_receipt_linked,
    ledger_visit_sealed,
    opened_gate_visit,
    write_receipt_to_run,
)
from tests.unit.shape_flow_helpers import shape_test_workspace
from tests.unit.snapshot_helpers import resolve_gate_at_node

BUNDLE = FOUNDRY_ROOT


def _base_verify_workspace(tmp_path: Path) -> tuple[Path, dict, dict, Path]:
    workspace = shape_test_workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "verify-evidence-001"
    run_dir.mkdir(parents=True)
    (run_dir / "artifacts").mkdir()
    (run_dir / "receipts").mkdir()

    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "verify-evidence-001",
        "run_uuid": TEST_RUN_UUID,
        "flow_id": IMPLEMENTATION_FLOW,
        "status": "running",
        "workspace": str(workspace),
        "config": {"workspace": str(workspace), "review": {"enabled": True}},
        "state": {
            "final_commit_sha": "abc123def456",
            "default_branch": "main",
            "feature_branch": "foundry/test-feature",
            "last_test_exit_code": 0,
            "approved_ac": "User can log in\nDashboard loads",
        },
        "visits": [],
        "ledger": [],
    }
    save_snapshot(run_dir, snapshot)
    return workspace, snapshot, flow, run_dir


@pytest.fixture
def verify_run(tmp_path: Path) -> tuple[Path, dict, dict, dict, Path]:
    workspace, snapshot, flow, run_dir = _base_verify_workspace(tmp_path)
    visit = admit_visit(
        snapshot,
        node_id=VERIFY_INTAKE_NODE,
        flow=flow,
        source="test",
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    save_snapshot(run_dir, snapshot)
    return workspace, snapshot, visit, flow, run_dir


@pytest.fixture
def quality_run(tmp_path: Path) -> tuple[Path, dict, dict, Path]:
    return _base_verify_workspace(tmp_path)


def test_verify_intake_blocked_missing_feature_branch(verify_run: tuple) -> None:
    workspace, snapshot, visit, flow, run_dir = verify_run
    state = snapshot.setdefault("state", {})
    if isinstance(state, dict):
        state.pop("feature_branch", None)

    result = run_verify_intake_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result.get("ok") is True
    assert result.get("transitioned") is False
    assert result.get("intake_status") == "blocked"
    assert "feature_branch missing" in result.get("findings", [])

    intake_path = run_dir / "receipts" / "intake.json"
    assert intake_path.is_file()
    intake = json.loads(intake_path.read_text(encoding="utf-8"))
    assert intake.get("status") == "blocked"


def test_acceptance_rework_execute_on_bad_diff(verify_run: tuple) -> None:
    _, snapshot, _, _, _ = verify_run
    decision, items, evidence_ok = _assess_acceptance(
        snapshot,
        "# branch diff unavailable: feature_branch missing\n",
    )
    assert decision == "rework_execute"
    assert evidence_ok is False
    assert items == []


def test_acceptance_does_not_pass_on_comment_substring_match(verify_run: tuple) -> None:
    _, snapshot, _, _, _ = verify_run
    diff = "+// User can log in via OAuth\n+// Dashboard loads metrics\n"
    decision, items, evidence_ok = _assess_acceptance(snapshot, diff)
    assert decision == "replan"
    assert evidence_ok is False
    assert all(item.get("status") == "not_verified" for item in items)


def test_verify_acceptance_agent_submit_publishes_findings_t5(quality_run: tuple) -> None:
    workspace, snapshot, flow, run_dir = quality_run
    acceptance_visit: dict = {
        "id": "v-acc-agent",
        "node_id": VERIFY_ACCEPTANCE_NODE,
        "kind": "step",
        "lifecycle": "opened",
        "outcome": None,
        "decision": None,
    }
    update_active_visit(snapshot, acceptance_visit)
    request_id = ensure_verify_acceptance_request(
        snapshot,
        acceptance_visit,
        flow,
        foundry_bundle=BUNDLE,
        workspace=workspace,
        run_dir=run_dir,
    )
    from foundry_cli.engine.wait_state import set_run_wait

    set_run_wait(
        snapshot,
        kind="agent",
        visit_id=str(acceptance_visit["id"]),
        summary="test",
        request_ref=request_id,
    )
    submit = submit_agent_result(
        snapshot,
        request_id=request_id,
        result=stub_verify_acceptance_result(
            gate_decision="pass",
            evidence_ok=True,
            items=[
                {
                    "criterion": "User can log in",
                    "status": "met",
                    "basis": "Tests passed.",
                    "evidence_refs": ["execute.test:exit-0"],
                },
                {
                    "criterion": "Dashboard loads",
                    "status": "met",
                    "basis": "Diff includes dashboard route.",
                    "evidence_refs": ["verify.intake.branch-diff"],
                },
            ],
        ),
        foundry_bundle=BUNDLE,
        visit=acceptance_visit,
        run_dir=run_dir,
    )
    assert submit.get("ok") is True
    complete = run_verify_acceptance_complete(
        snapshot,
        acceptance_visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert complete.get("ok") is True
    findings_path = run_dir / "artifacts" / "v-acc-agent" / "verify-findings.json"
    assert findings_path.is_file()
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    assert findings.get("gate_decision") == "pass"
    assert findings.get("evidence_ok") is True
    state = snapshot.get("state") or {}
    assert isinstance(state, dict)
    assert (state.get("verify_findings") or {}).get("gate_decision") == "pass"


def test_findings_from_acceptance_result_prefers_validator_gate_decision(verify_run: tuple) -> None:
    _, snapshot, _, _, _ = verify_run
    findings = findings_from_acceptance_result(
        snapshot,
        {
            "gate_decision": "reshape",
            "evidence_ok": False,
            "items": [
                {"criterion": "AC scope", "status": "not_met"},
                {"criterion": "Tests", "status": "not_met"},
            ],
            "summary": "reshape wins",
        },
    )
    assert findings.get("gate_decision") == "reshape"
    assert findings.get("evidence_ok") is False


def test_acceptance_env_override_ignored_when_stub_off(
    verify_run: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, snapshot, _, _, _ = verify_run
    monkeypatch.delenv("FOUNDRY_EXECUTE_STUB", raising=False)
    monkeypatch.setenv("FOUNDRY_VERIFY_ACCEPTANCE_DECISION", "replan")
    diff = "+unrelated change only\n"
    decision, _, _ = _resolve_acceptance_decision(snapshot, diff)
    assert decision == "replan"
    decision2, _, evidence_ok = _resolve_acceptance_decision(
        snapshot,
        "+User can log in\n+Dashboard loads\n",
    )
    assert decision2 == "replan"
    assert evidence_ok is False


def test_code_quality_non_stub_fails_without_manifest_command(
    verify_run: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, _, _, _, _ = verify_run
    monkeypatch.delenv("FOUNDRY_EXECUTE_STUB", raising=False)
    commands = _commands_for_code_quality(workspace)
    assert len(commands) == 1
    assert commands[0].get("exit_code") == 1
    assert "manifest" in str(commands[0].get("stderr", "")).lower()


def test_code_quality_gate_repair_when_stub_exit_code_one(
    quality_run: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, snapshot, flow, run_dir = quality_run
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    monkeypatch.setenv("FOUNDRY_EXECUTE_CODE_QUALITY_EXIT_CODE", "1")

    visit_cq: dict = {
        "id": "v-cq-001",
        "node_id": VERIFY_CODE_QUALITY_NODE,
        "kind": "step",
        "lifecycle": "opened",
        "outcome": None,
        "decision": None,
    }
    update_active_visit(snapshot, visit_cq)
    result = run_verify_code_quality_complete(
        snapshot,
        visit_cq,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result.get("ok") is True

    gate = resolve_gate_at_node(
        snapshot,
        flow,
        run_dir,
        "verify.code_quality.gate",
        visit=opened_gate_visit("v-cqg", "verify.code_quality.gate"),
    )
    assert gate.get("ok") is True
    assert gate.get("decision") == "repair"


def test_verify_acceptance_gate_routes_rework_when_evidence_not_ok(verify_run: tuple) -> None:
    _, snapshot, _, flow, run_dir = verify_run
    visit_id = "v-acc-001"
    findings = {
        "schema_version": "1.0.0",
        "gate_decision": "rework_execute",
        "evidence_ok": False,
        "items": [],
    }
    art_dir = run_dir / "artifacts" / visit_id
    art_dir.mkdir(parents=True, exist_ok=True)
    art_path = art_dir / "verify-findings.json"
    art_path.write_text(json.dumps(findings), encoding="utf-8")
    ledger = snapshot.setdefault("ledger", [])
    ledger.append(ledger_visit_sealed("verify.acceptance", visit_id=visit_id))
    ledger.append(
        ledger_artifact_linked(
            visit_id,
            artifact_id="verify-findings",
            uri=f"run:artifacts/{visit_id}/verify-findings.json",
        )
    )
    gate = resolve_gate_at_node(
        snapshot,
        flow,
        run_dir,
        "verify.acceptance.gate",
        visit=opened_gate_visit("v-acc-g", "verify.acceptance.gate"),
    )
    assert gate.get("ok") is True
    assert gate.get("decision") == "rework_execute"


def test_verify_acceptance_gate_blocks_pass_when_evidence_ok_missing(
    verify_run: tuple,
) -> None:
    _, snapshot, _, flow, run_dir = verify_run
    visit_id = "v-acc-003"
    findings = {
        "gate_decision": "pass",
        "items": [],
    }
    art_dir = run_dir / "artifacts" / visit_id
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "verify-findings.json").write_text(json.dumps(findings), encoding="utf-8")
    ledger = snapshot.setdefault("ledger", [])
    ledger.append(ledger_visit_sealed("verify.acceptance", visit_id=visit_id))
    ledger.append(
        ledger_artifact_linked(
            visit_id,
            artifact_id="verify-findings",
            uri=f"run:artifacts/{visit_id}/verify-findings.json",
        )
    )
    gate = resolve_gate_at_node(
        snapshot,
        flow,
        run_dir,
        "verify.acceptance.gate",
        visit=opened_gate_visit("v-acc-g3", "verify.acceptance.gate"),
    )
    assert gate.get("ok") is False


def test_verify_acceptance_gate_blocks_pass_when_evidence_not_ok(
    verify_run: tuple,
) -> None:
    _, snapshot, _, flow, run_dir = verify_run
    visit_id = "v-acc-002"
    findings = {
        "gate_decision": "pass",
        "evidence_ok": False,
        "items": [],
    }
    art_dir = run_dir / "artifacts" / visit_id
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "verify-findings.json").write_text(json.dumps(findings), encoding="utf-8")
    ledger = snapshot.setdefault("ledger", [])
    ledger.append(ledger_visit_sealed("verify.acceptance", visit_id=visit_id))
    ledger.append(
        ledger_artifact_linked(
            visit_id,
            artifact_id="verify-findings",
            uri=f"run:artifacts/{visit_id}/verify-findings.json",
        )
    )
    gate = resolve_gate_at_node(
        snapshot,
        flow,
        run_dir,
        "verify.acceptance.gate",
        visit=opened_gate_visit("v-acc-g2", "verify.acceptance.gate"),
    )
    assert gate.get("ok") is False
    assert gate.get("code") == "EVIDENCE_MISSING"


def test_verify_intake_gate_rejects_blocked_receipt(verify_run: tuple) -> None:
    _, snapshot, visit, flow, run_dir = verify_run
    intake = intake_receipt_body(
        VERIFY_INTAKE_NODE,
        status="blocked",
        receipt_id="r-blocked",
        checks=[],
    )
    visit_id = str(visit["id"])
    uri = write_receipt_to_run(run_dir, visit_id, INTAKE_RECEIPT_SCHEMA, intake)
    ledger = snapshot.setdefault("ledger", [])
    ledger.append(ledger_visit_sealed(VERIFY_INTAKE_NODE, visit_id=visit_id))
    ledger.append(
        ledger_receipt_linked(
            visit_id,
            schema=INTAKE_RECEIPT_SCHEMA,
            path=uri,
            receipt_id="r-blocked",
        )
    )
    gate = resolve_gate_at_node(
        snapshot,
        flow,
        run_dir,
        "verify.intake.gate",
        visit=opened_gate_visit("v-int-g", "verify.intake.gate"),
    )
    assert gate.get("ok") is False


def test_verify_intake_rejects_sha_not_on_feature_branch(tmp_path: Path) -> None:
    import subprocess

    workspace = tmp_path / "app"
    workspace.mkdir()
    (workspace / "readme.md").write_text("seed\n", encoding="utf-8")
    init_clean_git_repo(workspace)
    subprocess.run(["git", "checkout", "-b", "foundry/feature"], cwd=workspace, check=True, capture_output=True)
    (workspace / "feature.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature.txt"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feature work"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "main moves on"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )
    main_head = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    diff = subprocess.run(
        ["git", "diff", "main...foundry/feature"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    snapshot = {
        "state": {
            "final_commit_sha": main_head,
            "feature_branch": "foundry/feature",
            "default_branch": "main",
        }
    }
    findings = _validate_verify_intake_context(snapshot, workspace, diff)
    assert findings


def test_verify_code_quality_skipped_when_review_disabled(
    quality_run: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, snapshot, flow, run_dir = quality_run
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    config = snapshot.setdefault("config", {})
    if isinstance(config, dict):
        config["review"] = {"enabled": False}

    visit_cq: dict = {
        "id": "v-cq-skip",
        "node_id": VERIFY_CODE_QUALITY_NODE,
        "kind": "step",
        "lifecycle": "opened",
        "outcome": None,
        "decision": None,
    }
    update_active_visit(snapshot, visit_cq)
    result = run_verify_code_quality_complete(
        snapshot,
        visit_cq,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result.get("ok") is True
    gate = resolve_gate_at_node(
        snapshot,
        flow,
        run_dir,
        "verify.code_quality.gate",
        visit=opened_gate_visit("v-cqg-skip", "verify.code_quality.gate"),
    )
    assert gate.get("decision") == "pass"
    assert gate.get("rule_id") == "verify.code_quality.gate/skipped"


def test_verify_code_review_complete_publishes_notes_and_transitions(
    quality_run: tuple,
) -> None:
    workspace, snapshot, flow, run_dir = quality_run
    visit_id = "v-cr-001"
    visit_cr: dict = {
        "id": visit_id,
        "node_id": VERIFY_CODE_REVIEW_NODE,
        "kind": "step",
        "lifecycle": "opened",
        "outcome": None,
        "decision": None,
    }
    update_active_visit(snapshot, visit_cr)
    result = run_verify_code_review_complete(
        snapshot,
        visit_cr,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result.get("ok") is True
    notes_path = run_dir / "artifacts" / visit_id / "verify-notes.md"
    assert notes_path.is_file()
    assert "foundry/test-feature" in notes_path.read_text(encoding="utf-8")
    state = snapshot.get("state") or {}
    assert isinstance(state, dict)
    assert state.get("verify_notes")
    sealed = [e for e in snapshot.get("ledger", []) if e.get("type") == "visit.sealed"]
    assert any(e.get("node_id") == VERIFY_CODE_REVIEW_NODE for e in sealed)


def test_verify_complete_patches_verified_at_and_transitions(quality_run: tuple) -> None:
    workspace, snapshot, flow, run_dir = quality_run
    visit_id = "v-vc-001"
    visit_vc: dict = {
        "id": visit_id,
        "node_id": VERIFY_COMPLETE_NODE,
        "kind": "step",
        "lifecycle": "opened",
        "outcome": None,
        "decision": None,
    }
    update_active_visit(snapshot, visit_vc)
    result = run_verify_complete_complete(
        snapshot,
        visit_vc,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result.get("ok") is True
    state = snapshot.get("state") or {}
    assert isinstance(state, dict)
    assert state.get("verified_at")
    sealed = [e for e in snapshot.get("ledger", []) if e.get("type") == "visit.sealed"]
    assert any(e.get("node_id") == VERIFY_COMPLETE_NODE for e in sealed)
