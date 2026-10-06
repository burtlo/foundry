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


def test_boundary_wait_execute_intake_is_unsupported_operator(tmp_path: Path) -> None:
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
    assert isinstance(wait, dict)
    assert wait.get("kind") == "operator"
    assert wait.get("request_ref") == "unsupported:execute.intake"
    summary = str(wait.get("summary") or "")
    assert "not yet implemented" in summary.lower()
    assert "steward" not in summary.lower()


def test_advance_at_execute_intake_after_authorization_yields_unsupported_wait(
    tmp_path: Path,
) -> None:
    """Simulates post-`foundry start` position: opened visit at execute.intake."""
    workspace = _workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "adv-exec-intake-adv"
    run_dir.mkdir(parents=True)
    visit = {
        "id": "v-exec-intake-adv",
        "node_id": "execute.intake",
        "kind": "step",
        "lifecycle": "opened",
    }
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-exec-intake-adv",
        "flow_id": "implementation",
        "status": "running",
        "revision": 1,
        "workspace": str(workspace),
        "config": {"workspace": str(workspace)},
        "state": {},
        "visits": [visit],
        "active_visit": visit,
        "ledger": [],
        "wait": None,
    }
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
    assert wait.get("request_ref") == "unsupported:execute.intake"


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


def test_boundary_wait_shape_present_allows_host_advance(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "adv-present"
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-present",
        "status": "running",
        "visits": [],
        "ledger": [],
        "wait": None,
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
    assert wait is None


def test_boundary_wait_shape_record_allows_host_advance(tmp_path: Path) -> None:
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
    assert wait is None


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
