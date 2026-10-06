"""Workflow-02 slice 2A: execute.intake through execute.plan."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.gates import resolve_engine_gate_decision
from foundry_cli.registry import load_registry
from foundry_cli.run_service import execute_start_durable
from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.git_workspace import ensure_clean_git_workspace

BUNDLE = FOUNDRY_ROOT
FIXTURE_RECORD_GATE = "porcelain-0007-v007-record-gate"
CLI = BUNDLE / "cli" / "foundry.py"


def _workspace_with_fixture(tmp_path: Path, fixture_name: str) -> tuple[Path, str]:
    src = BUNDLE / "fixtures" / "runs" / fixture_name
    snapshot = json.loads((src / "snapshot.json").read_text(encoding="utf-8"))
    run_id = str(snapshot.get("run_id") or fixture_name)
    workspace = tmp_path / "app"
    dest = workspace / ".foundry" / "runs" / run_id
    shutil.copytree(src, dest)
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
        dirs_exist_ok=True,
    )
    ensure_clean_git_workspace(workspace)
    return workspace, run_id


def _run_cli(workspace: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--json",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            *argv,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _authorize_execute(workspace: Path, run_id: str) -> None:
    decide = _run_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
    assert decide.returncode == 0, decide.stderr + decide.stdout
    advance = _run_cli(workspace, "run", "advance", "--run", run_id)
    assert advance.returncode == 0, advance.stderr + advance.stdout
    body = json.loads(advance.stdout)
    assert body.get("active_node_id") == "execute.start"
    ensure_clean_git_workspace(workspace)
    start = execute_start_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_id=run_id,
    )
    assert start.get("ok") is True, start
    assert start.get("active_node_id") == "execute.intake"


def test_execute_intake_gate_passes_on_passed_receipt(tmp_path: Path) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _authorize_execute(workspace, run_id)
    ensure_clean_git_workspace(workspace)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    result = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=12,
    )
    assert result["reason"] != "execution_error"
    assert snapshot.get("status") == "running"
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") in {"execute.branch", "execute.plan", "execute.build"}
    state = snapshot.get("state") or {}
    assert state.get("feature_branch", "").startswith("foundry/")
    assert state.get("execution_graph_id")

    gate_visit = next(
        (v for v in snapshot.get("visits", []) if v.get("node_id") == "execute.intake.gate"),
        None,
    )
    assert gate_visit is not None
    assert gate_visit.get("decision") == "pass"

    if active.get("node_id") == "execute.build":
        wait = snapshot.get("wait")
        assert wait is None


def test_boundary_wait_execute_intake_allows_host_advance(tmp_path: Path) -> None:
    from foundry_cli.engine.advance import _boundary_wait_for_visit

    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    visit = {
        "id": "v-intake",
        "node_id": "execute.intake",
        "kind": "step",
        "lifecycle": "opened",
    }
    wait = _boundary_wait_for_visit(
        snapshot={"status": "running", "ledger": [], "wait": None},
        visit=visit,
        flow=flow,
        foundry_bundle=BUNDLE,
        workspace=workspace,
        run_dir=run_dir,
    )
    assert wait is None


def test_execute_intake_gate_rejects_blocked_receipt(tmp_path: Path) -> None:
    from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
    from foundry_cli.engine.receipts import seal_receipt_path
    from foundry_cli.paths import resolve_run_uri

    intake_visit_id = "v-ei"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uri = seal_receipt_path(INTAKE_RECEIPT_SCHEMA, intake_visit_id)
    path = resolve_run_uri(uri, run_dir, intake_visit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "2.2.0",
        "receipt_id": "00000000-0000-4000-8000-000000000010",
        "run_id": "00000000-0000-4000-8000-000000000099",
        "timestamp": "2026-01-01T00:00:00Z",
        "step_id": "execute.intake",
        "status": "blocked",
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
    visit = {"id": "v-g", "node_id": "execute.intake.gate", "kind": "gate", "lifecycle": "opened"}
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
    assert result["ok"] is False
    assert result["code"] == "EVIDENCE_MISSING"
