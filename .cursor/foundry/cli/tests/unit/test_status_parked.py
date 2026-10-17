"""Human foundry status and run.get parked projection (P2 run block visibility)."""

from __future__ import annotations

import argparse
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

from foundry import _format_status
from foundry_cli.engine.blocked_intake import BLOCKED_INTAKE_STATUS_CODE
from foundry_cli.engine.run_status_reason import set_status_reason
from foundry_cli.host.handlers import HostHandlers
from foundry_cli.run_service import get_run
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import intake_open_run, shape_test_workspace

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


def _capture_status(result: dict) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        _format_status(argparse.Namespace(), result)
    return buf.getvalue()


def test_format_status_prints_parked_record_and_commands() -> None:
    parked = {
        "heading": "Action",
        "step_title": "Execute intake",
        "node_id": "execute.intake",
        "reason_code": BLOCKED_INTAKE_STATUS_CODE,
        "message": "Missing plan; No tests",
        "findings": ["Missing plan", "No tests"],
        "commands": ["foundry run advance --run foundry-test"],
    }
    result = {"run_id": "foundry-test", "parked": parked}
    out = _capture_status(result)
    assert "step=Execute intake" in out
    assert "node=execute.intake" in out
    assert f"code={BLOCKED_INTAKE_STATUS_CODE}" in out
    assert "Missing plan; No tests" in out
    assert "- Missing plan" in out
    assert "- No tests" in out
    assert out.strip().endswith("foundry run advance --run foundry-test")
    assert "run=foundry-test" not in out


def test_format_status_halt_without_commands_omits_command_hints() -> None:
    parked = {
        "heading": "Definition error",
        "step_title": "Shape intake",
        "node_id": "shape.intake",
        "message": "Flow definition is invalid",
        "findings": [],
        "commands": [],
    }
    out = _capture_status({"parked": parked})
    assert "Flow definition is invalid" in out
    assert "foundry " not in out


def test_format_status_agent_wait_keeps_short_identity_line(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, flow = intake_open_run(workspace, work_prompt="Agent wait status")
    from foundry_cli.engine.advance import advance_run
    from foundry_cli.run_store import get_revision, commit_snapshot

    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    commit_snapshot(run_dir, snapshot, expected_revision=get_revision(snapshot), bump=True)
    run_id = str(snapshot.get("run_id"))
    payload = get_run(workspace, run_id=run_id, bundle=BUNDLE)
    assert payload.get("ok") is True
    assert payload.get("parked") is None
    assert payload.get("status_reason") is None or isinstance(payload.get("status_reason"), dict)

    out = _capture_status(payload)
    assert f"run={run_id}" in out
    assert "wait=agent" in out
    assert "foundry retry" not in out


def test_get_run_includes_parked_for_blocked_intake(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Blocked status")
    findings = ["Missing plan"]
    _write_assessment(run_dir, findings)
    set_status_reason(snapshot, BLOCKED_INTAKE_STATUS_CODE, message="; ".join(findings))
    snapshot["wait"] = {
        "kind": "operator",
        "visit_id": snapshot["active_visit"]["id"],
        "summary": "Intake blocked",
    }
    save_snapshot(run_dir, snapshot)
    run_id = str(snapshot.get("run_id"))

    payload = get_run(workspace, run_id=run_id, bundle=BUNDLE)
    assert payload.get("ok") is True
    parked = payload.get("parked")
    assert isinstance(parked, dict)
    assert parked.get("reason_code") == BLOCKED_INTAKE_STATUS_CODE
    assert parked.get("findings") == findings
    assert parked.get("commands") == [f"foundry run advance --run {run_id}"]

    out = _capture_status(payload)
    assert f"foundry run advance --run {run_id}" in out


def test_host_run_get_includes_parked_key(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Host parked")
    run_id = str(snapshot.get("run_id"))
    handlers = HostHandlers(workspace, BUNDLE)
    result = handlers.run_get({"run_id": run_id})
    assert result.get("ok") is True
    assert "parked" in result
    assert result.get("parked") is None
