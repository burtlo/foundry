"""Unit tests for visit present complete executor."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.agent.submit import submit_agent_result
from foundry_cli.engine.shape_step_executor import run_shape_present_complete
from foundry_cli.registry import load_registry
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import NODE_SHAPE_EXAMINE, NODE_SHAPE_INTAKE, NODE_SHAPE_PRESENT
from tests.unit.test_advance import _intake_open_run
from tests.unit.test_agent_connection import _valid_result

BUNDLE = FOUNDRY_ROOT


def _valid_presentation_result(**overrides: object) -> dict:
    body = {
        "summary": "PROCEED: presentation ready.",
        "verdict": "PROCEED",
        "presented_ac": "User can publish presentation markdown.",
        "presentation_markdown": "# Plan\n\n## AC\n\nUser can publish presentation markdown.\n",
    }
    body.update(overrides)
    return body


def _present_opened_run(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Present complete tests")
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
        result=_valid_result(questions=[]),
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
        result=_valid_presentation_result(),
        foundry_bundle=BUNDLE,
        visit=visit,
        run_dir=run_dir,
        workspace=workspace,
    )
    save_snapshot(run_dir, snapshot)
    return run_dir, snapshot, visit, flow


def test_implementation_flow_shape_present_allow_cli() -> None:
    _, flow = load_registry(BUNDLE)
    present = next(node for node in flow["nodes"] if node.get("id") == NODE_SHAPE_PRESENT)
    assert present["allow"]["cli"] == ["run.agent.submit", "visit.present.complete"]
    assert "worker" not in present
    assert "questions_asked_total" not in (present.get("reads", {}).get("state") or [])


def test_present_complete_happy_path(tmp_path: Path) -> None:
    run_dir, snapshot, visit, flow = _present_opened_run(tmp_path)
    workspace = Path(snapshot["workspace"])
    result = run_shape_present_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is True
    assert result["next_node_id"] == "shape.present.gate"
    agent = json.loads((run_dir / "receipts" / "agent.json").read_text(encoding="utf-8"))
    assert agent["recommended_next_state"] == "shape.present.gate"
    presentation = run_dir / "artifacts" / str(visit["id"]) / "presentation.md"
    assert presentation.is_file()


def test_present_complete_judgment_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "present-missing"
    run_dir.mkdir(parents=True)
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "present-missing",
        "status": "running",
        "visits": [],
        "ledger": [],
        "active_visit": {
            "id": "v-present",
            "node_id": NODE_SHAPE_PRESENT,
            "kind": "step",
            "lifecycle": "opened",
        },
    }
    visit = snapshot["active_visit"]
    result = run_shape_present_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is False
    assert result["code"] == "JUDGMENT_MISSING"
