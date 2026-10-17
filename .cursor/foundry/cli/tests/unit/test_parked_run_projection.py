"""Parked-run projection (P1 run block visibility)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_cli.engine.blocked_intake import BLOCKED_INTAKE_STATUS_CODE
from foundry_cli.engine.operator import EXECUTE_START_NODE_ID
from foundry_cli.engine.run_status_reason import set_status_reason
from foundry_cli.parked_run import build_parked_run_projection
from foundry_cli.registry import load_registry
from foundry_cli.run_labels import node_step_title
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def _write_assessment(run_dir: Path, findings: list[str]) -> None:
    lines = [
        "# Intake assessment",
        "",
        "**Verdict:** BLOCKED",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {item}" for item in findings)
    lines.append("")
    receipts = run_dir / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / "assessment.md").write_text("\n".join(lines), encoding="utf-8")


def _base_snapshot(*, run_id: str = "foundry-test", status: str = "running") -> dict:
    return {
        "run_id": run_id,
        "status": status,
        "active_visit": {"id": "v1", "node_id": "execute.intake", "kind": "step", "lifecycle": "opened"},
    }


@pytest.fixture(scope="module")
def flow() -> dict:
    _, materialized = load_registry(BUNDLE)
    return materialized


def test_agent_wait_returns_null(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = _base_snapshot()
    snapshot["wait"] = {"kind": "agent", "visit_id": "v1", "summary": "Agent working"}
    assert build_parked_run_projection(snapshot, flow, run_dir) is None


def test_idle_running_returns_null(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = _base_snapshot(status="running")
    snapshot.pop("wait", None)
    assert build_parked_run_projection(snapshot, flow, run_dir) is None


def test_completed_returns_null(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = _base_snapshot(status="completed")
    snapshot["wait"] = {"kind": "operator", "visit_id": "v1", "summary": "Should not show"}
    assert build_parked_run_projection(snapshot, flow, run_dir) is None


def test_blocked_execute_intake_advance_and_findings(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    findings = ["approved_ac missing", "plan_path missing"]
    _write_assessment(run_dir, findings)
    snapshot = _base_snapshot()
    set_status_reason(snapshot, BLOCKED_INTAKE_STATUS_CODE, message="; ".join(findings))
    snapshot["wait"] = {
        "kind": "operator",
        "visit_id": "v1",
        "summary": "execute.intake is blocked; fix run state",
    }
    with patch("foundry_cli.engine.blocked_intake.intake_validation_findings") as mocked:
        parked = build_parked_run_projection(snapshot, flow, run_dir)
        mocked.assert_not_called()

    assert parked is not None
    assert parked["heading"] == "Action"
    assert parked["node_id"] == "execute.intake"
    assert parked["step_title"] == node_step_title("execute.intake", flow)
    assert parked["reason_code"] == BLOCKED_INTAKE_STATUS_CODE
    assert parked["message"] == "; ".join(findings)
    assert parked["findings"] == findings
    assert parked["commands"] == ["foundry run advance --run foundry-test"]


def test_blocked_verify_intake_same_shape(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    findings = ["feature_branch missing"]
    _write_assessment(run_dir, findings)
    snapshot = _base_snapshot()
    snapshot["active_visit"]["node_id"] = "verify.intake"
    set_status_reason(snapshot, BLOCKED_INTAKE_STATUS_CODE, message="; ".join(findings))
    snapshot["wait"] = {
        "kind": "operator",
        "visit_id": "v1",
        "summary": "verify.intake is blocked; fix run state",
    }
    parked = build_parked_run_projection(snapshot, flow, run_dir)
    assert parked is not None
    assert parked["node_id"] == "verify.intake"
    assert parked["findings"] == findings
    assert parked["commands"] == ["foundry run advance --run foundry-test"]


def test_repair_limit_paused_retry_no_advance(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = _base_snapshot(status="paused")
    snapshot["active_visit"]["node_id"] = "execute.repair.limit.gate"
    set_status_reason(snapshot, "REPAIR_LIMIT_EXCEEDED", message="Repair loop limit exceeded")
    parked = build_parked_run_projection(snapshot, flow, run_dir)
    assert parked is not None
    assert parked["heading"] == "Paused"
    assert parked["reason_code"] == "REPAIR_LIMIT_EXCEEDED"
    assert parked["commands"] == ["foundry retry foundry-test"]
    assert not any("advance" in line for line in parked["commands"])


def test_gate_decide_lines(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = _base_snapshot()
    snapshot["active_visit"] = {
        "id": "v-gate",
        "node_id": "shape.present.gate",
        "kind": "gate",
        "lifecycle": "opened",
    }
    snapshot["wait"] = {
        "kind": "decision",
        "visit_id": "v-gate",
        "summary": "Approve plan presentation",
    }
    parked = build_parked_run_projection(snapshot, flow, run_dir)
    assert parked is not None
    assert parked["heading"] == "Approval"
    assert parked["commands"] == [
        "foundry decide foundry-test reject",
        "foundry decide foundry-test accept",
    ]
    assert not any("start" in line for line in parked["commands"])


def test_question_wait_answer_command(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = _base_snapshot()
    snapshot["active_visit"]["node_id"] = "shape.examine"
    snapshot["wait"] = {
        "kind": "user_input",
        "visit_id": "v1",
        "summary": "Answer clarifying questions",
    }
    parked = build_parked_run_projection(snapshot, flow, run_dir)
    assert parked is not None
    assert parked["heading"] == "Answers"
    assert parked["commands"] == ["foundry answer foundry-test"]


def test_execute_start_only_start_command(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = _base_snapshot()
    snapshot["active_visit"] = {
        "id": "v-start",
        "node_id": EXECUTE_START_NODE_ID,
        "kind": "gate",
        "lifecycle": "opened",
    }
    snapshot["wait"] = {
        "kind": "decision",
        "visit_id": "v-start",
        "summary": "Authorize execute",
    }
    parked = build_parked_run_projection(snapshot, flow, run_dir)
    assert parked is not None
    assert parked["node_id"] == EXECUTE_START_NODE_ID
    assert parked["commands"] == ["foundry start foundry-test"]
    assert not any("decide" in line for line in parked["commands"])


def test_halt_no_legal_commands(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = _base_snapshot(status="definition_error")
    snapshot["active_visit"]["node_id"] = "execute.build"
    set_status_reason(snapshot, "DEFINITION_ERROR", message="Flow definition is invalid")
    parked = build_parked_run_projection(snapshot, flow, run_dir)
    assert parked is not None
    assert parked["heading"] == "Definition error"
    assert parked["message"] == "Flow definition is invalid"
    assert parked["commands"] == []


def test_findings_empty_when_assessment_missing(flow: dict, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = _base_snapshot(status="paused")
    set_status_reason(snapshot, "REPAIR_LIMIT_EXCEEDED", message="Repair loop limit exceeded")
    parked = build_parked_run_projection(snapshot, flow, run_dir)
    assert parked is not None
    assert parked["findings"] == []
