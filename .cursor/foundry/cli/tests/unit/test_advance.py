"""Unit tests for run advance boundaries and revision."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from foundry_cli.engine.advance import _boundary_wait_for_visit, advance_run
from foundry_cli.engine.lifecycle import admit_visit
from foundry_cli.registry import load_registry
from foundry_cli.run_store import get_revision, load_snapshot, save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import (
    NODE_SHAPE_EXAMINE,
    NODE_SHAPE_INTAKE,
    NODE_SHAPE_PRESENT,
    NODE_SHAPE_RECORD,
)

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    return workspace


def _intake_open_run(workspace: Path, *, work_prompt: str | None) -> tuple[Path, dict, dict]:
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "adv-0001"
    run_dir.mkdir(parents=True)
    (run_dir / "artifacts").mkdir()
    (run_dir / "receipts").mkdir()
    config: dict = {"workspace": str(workspace)}
    if work_prompt:
        config["shape"] = {"work_prompt": work_prompt}
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-0001",
        "run_uuid": "00000000-0000-4000-8000-000000000099",
        "flow_id": "implementation",
        "status": "running",
        "revision": 1,
        "workspace": str(workspace),
        "config": config,
        "state": {"ticket": None, "app_folder": None},
        "visits": [],
        "ledger": [],
        "wait": None,
    }
    visit = admit_visit(
        snapshot,
        node_id=NODE_SHAPE_INTAKE,
        flow=flow,
        source="test",
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    save_snapshot(run_dir, snapshot)
    return run_dir, snapshot, flow


def test_boundary_wait_execute_start_is_decision(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-exec-start",
        "status": "running",
        "visits": [],
        "ledger": [],
        "wait": None,
    }
    visit = {
        "id": "v-exec-start",
        "node_id": "execute.start",
        "kind": "gate",
        "lifecycle": "opened",
    }
    wait = _boundary_wait_for_visit(
        snapshot,
        visit,
        flow,
        foundry_bundle=BUNDLE,
        workspace=workspace,
        run_dir=workspace / ".foundry" / "runs" / "adv-exec-start",
    )
    assert isinstance(wait, dict)
    assert wait.get("kind") == "decision"
    assert wait.get("request_ref") == "gate:execute.start"


def test_boundary_wait_execute_branch_allows_host_advance(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-exec-branch",
        "status": "running",
        "visits": [],
        "ledger": [],
        "wait": None,
    }
    visit = {
        "id": "v-exec-branch",
        "node_id": "execute.branch",
        "kind": "step",
        "lifecycle": "opened",
    }
    wait = _boundary_wait_for_visit(
        snapshot,
        visit,
        flow,
        foundry_bundle=BUNDLE,
        workspace=workspace,
        run_dir=workspace / ".foundry" / "runs" / "adv-exec-branch",
    )
    assert wait is None


def test_boundary_wait_execute_intake_allows_host_advance(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-exec-intake",
        "status": "running",
        "visits": [],
        "ledger": [],
        "wait": None,
    }
    visit = {
        "id": "v-exec-intake",
        "node_id": "execute.intake",
        "kind": "step",
        "lifecycle": "opened",
    }
    wait = _boundary_wait_for_visit(
        snapshot,
        visit,
        flow,
        foundry_bundle=BUNDLE,
        workspace=workspace,
        run_dir=workspace / ".foundry" / "runs" / "adv-exec-intake",
    )
    assert wait is None


def test_boundary_wait_verify_intake_allows_host_advance(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-verify-intake",
        "status": "running",
        "visits": [],
        "ledger": [],
        "wait": None,
    }
    visit = {
        "id": "v-verify-intake",
        "node_id": "verify.intake",
        "kind": "step",
        "lifecycle": "opened",
    }
    wait = _boundary_wait_for_visit(
        snapshot,
        visit,
        flow,
        foundry_bundle=BUNDLE,
        workspace=workspace,
        run_dir=workspace / ".foundry" / "runs" / "adv-verify-intake",
    )
    assert wait is None


def test_advance_missing_work_prompt_sets_operator_wait(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt=None)
    result = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["reason"] == "wait"
    wait = snapshot.get("wait")
    assert isinstance(wait, dict)
    assert wait.get("kind") == "operator"
    assert wait.get("visit_id") == snapshot["active_visit"]["id"]


def test_boundary_wait_shape_present_requires_agent_judgment(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "adv-present"
    run_dir.mkdir(parents=True)
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-present",
        "status": "running",
        "visits": [],
        "ledger": [],
        "wait": None,
        "state": {"draft_ac": "AC", "ticket": {"raw_input": "x"}},
    }
    visit = {
        "id": "v-present",
        "node_id": NODE_SHAPE_PRESENT,
        "kind": "step",
        "lifecycle": "opened",
    }
    wait = _boundary_wait_for_visit(
        snapshot,
        visit,
        flow,
        foundry_bundle=BUNDLE,
        workspace=workspace,
        run_dir=run_dir,
    )
    assert wait is not None
    assert wait.get("kind") == "agent"


def test_boundary_wait_sealed_non_terminal_without_connection_stays_running(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "adv-record-gate-sealed"
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-record-gate-sealed",
        "status": "running",
        "visits": [],
        "ledger": [
            {
                "type": "visit.sealed",
                "visit_id": "v-007",
                "node_id": "shape.record.gate",
                "payload": {"outcome": "completed"},
            }
        ],
        "wait": None,
    }
    visit = {
        "id": "v-007",
        "node_id": "shape.record.gate",
        "kind": "gate",
        "lifecycle": "sealed",
        "decision": "hold",
    }
    wait = _boundary_wait_for_visit(
        snapshot,
        visit,
        flow,
        foundry_bundle=BUNDLE,
        workspace=workspace,
        run_dir=run_dir,
    )
    assert wait is None
    assert snapshot["status"] == "running"


def test_boundary_wait_shape_record_emits_agent_wait(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "adv-record"
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-record",
        "status": "running",
        "visits": [],
        "ledger": [],
        "wait": None,
        "state": {
            "presented_ac": "AC",
            "presentation_artifact_path": "run:artifacts/v-present/presentation.md",
        },
    }
    visit = {
        "id": "v-record",
        "node_id": NODE_SHAPE_RECORD,
        "kind": "step",
        "lifecycle": "opened",
    }
    wait = _boundary_wait_for_visit(
        snapshot,
        visit,
        flow,
        foundry_bundle=BUNDLE,
        workspace=workspace,
        run_dir=run_dir,
    )
    assert wait is not None
    assert wait.get("kind") == "agent"


def test_advance_intake_completes_then_waits_at_examine(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Add durable advance")
    result = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["steps_taken"] >= 1
    assert snapshot["active_visit"]["node_id"] == NODE_SHAPE_EXAMINE
    wait = snapshot.get("wait")
    assert isinstance(wait, dict)
    assert wait.get("kind") == "agent"


def test_advance_idempotent_without_revision_bump(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt=None)
    first = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert first["mutated"] is True
    save_snapshot(run_dir, snapshot)
    revision_after_first = get_revision(snapshot)
    reloaded = load_snapshot(run_dir)
    second = advance_run(
        reloaded,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert second["mutated"] is False
    assert second["reason"] == "wait"
    assert get_revision(reloaded) == revision_after_first


def test_run_recover_subprocess_after_create(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    create = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--json",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            "run",
            "create",
            "--work-prompt",
            "Resume after fresh process",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert create.returncode == 0, create.stderr
    payload = json.loads(create.stdout)
    run_id = payload["run_id"]
    recover = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--json",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            "run",
            "recover",
            "--run",
            run_id,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert recover.returncode == 0, recover.stderr
    body = json.loads(recover.stdout)
    assert body.get("recovered") is True
    assert body.get("active_node_id") == "shape.present.gate"
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    wait = snapshot.get("wait")
    assert isinstance(wait, dict)
    assert wait.get("kind") == "decision"
    assert body.get("revision", 0) >= 2
