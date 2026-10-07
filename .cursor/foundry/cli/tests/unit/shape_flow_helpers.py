"""Shape-phase fixture workspaces and intake → record advance chains."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from foundry_cli.engine import decide_gate
from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.agent.adapter import default_stub_examination_result
from foundry_cli.engine.agent.submit import submit_agent_result
from foundry_cli.engine.lifecycle import admit_visit
from foundry_cli.engine.shape_step_executor import run_shape_present_complete
from foundry_cli.registry import load_registry
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import (
    IMPLEMENTATION_FLOW,
    NODE_SHAPE_INTAKE,
    NODE_SHAPE_PRESENT,
    NODE_SHAPE_RECORD,
    TEST_RUN_UUID,
)

BUNDLE = FOUNDRY_ROOT


def shape_test_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    return workspace


def intake_open_run(workspace: Path, *, work_prompt: str | None) -> tuple[Path, dict, dict]:
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
        "run_uuid": TEST_RUN_UUID,
        "flow_id": IMPLEMENTATION_FLOW,
        "status": "running",
        "revision": 1,
        "workspace": str(workspace),
        "config": config,
        "state": {"ticket": None, "app_folder": None},
        "visits": [],
        "ledger": [],
        "wait": None,
    }
    admit_visit(
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


def valid_examination_result(**overrides: object) -> dict[str, Any]:
    body = default_stub_examination_result()
    body.update(overrides)
    return body


def valid_presentation_result(**overrides: object) -> dict[str, Any]:
    body = {
        "summary": "PROCEED: presentation ready.",
        "verdict": "PROCEED",
        "presented_ac": "User can publish presentation markdown.",
        "presentation_markdown": "# Plan\n\n## AC\n\nUser can publish presentation markdown.\n",
    }
    body.update(overrides)
    return body


def valid_record_result(**overrides: object) -> dict[str, Any]:
    body = {
        "summary": "PROCEED: plan ready.",
        "verdict": "PROCEED",
        "approved_ac": "User can publish plan markdown.",
        "plan_markdown": "# Living plan\n\n## AC\n\nUser can publish plan markdown.\n",
    }
    body.update(overrides)
    return body


def present_opened_run(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, flow = intake_open_run(workspace, work_prompt="Present complete tests")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    wait = snapshot.get("wait")
    assert isinstance(wait, dict) and wait.get("kind") == "agent"
    request_id = str(wait["request_ref"])
    submit_agent_result(
        snapshot,
        request_id=request_id,
        result=valid_examination_result(questions=[]),
        foundry_bundle=BUNDLE,
    )
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    visit = snapshot["active_visit"]
    assert visit["node_id"] == NODE_SHAPE_PRESENT
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    wait = snapshot.get("wait")
    assert isinstance(wait, dict) and wait.get("kind") == "agent"
    request_id = str(wait["request_ref"])
    submit_agent_result(
        snapshot,
        request_id=request_id,
        result=valid_presentation_result(),
        foundry_bundle=BUNDLE,
        visit=visit,
        run_dir=run_dir,
        workspace=workspace,
    )
    save_snapshot(run_dir, snapshot)
    return run_dir, snapshot, visit, flow


def record_opened_run(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    run_dir, snapshot, visit, flow = present_opened_run(tmp_path)
    workspace = tmp_path / "app"
    present_result = run_shape_present_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert present_result.get("ok") is True
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    visit = snapshot["active_visit"]
    assert visit["node_id"] == "shape.present.gate"
    gate_result = decide_gate(
        snapshot,
        visit,
        flow,
        decision="accept",
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert gate_result.get("ok") is True
    visit = snapshot["active_visit"]
    assert visit["node_id"] == NODE_SHAPE_RECORD
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    wait = snapshot.get("wait")
    assert isinstance(wait, dict) and wait.get("kind") == "agent"
    request_id = str(wait["request_ref"])
    submit_agent_result(
        snapshot,
        request_id=request_id,
        result=valid_record_result(),
        foundry_bundle=BUNDLE,
        visit=visit,
        run_dir=run_dir,
        workspace=workspace,
    )
    save_snapshot(run_dir, snapshot)
    return run_dir, snapshot, visit, flow
