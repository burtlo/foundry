"""Unit tests for visit record complete executor."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from foundry_cli.engine.agent.submit import submit_agent_result
from foundry_cli.engine.shape_step_executor import run_shape_record_complete
from foundry_cli.registry import load_registry
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import NODE_SHAPE_RECORD
from tests.unit.test_shape_present_complete import _present_opened_run

BUNDLE = FOUNDRY_ROOT


def _valid_record_result(**overrides: object) -> dict:
    body = {
        "summary": "PROCEED: plan ready.",
        "verdict": "PROCEED",
        "approved_ac": "User can publish plan markdown.",
        "plan_markdown": "# Living plan\n\n## AC\n\nUser can publish plan markdown.\n",
    }
    body.update(overrides)
    return body


def _record_opened_run(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    run_dir, snapshot, visit, flow = _present_opened_run(tmp_path)
    workspace = tmp_path / "app"
    from foundry_cli.engine.advance import advance_run
    from foundry_cli.engine import decide_gate
    from foundry_cli.engine.shape_step_executor import run_shape_present_complete

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
        result=_valid_record_result(),
        foundry_bundle=BUNDLE,
        visit=visit,
        run_dir=run_dir,
        workspace=workspace,
    )
    save_snapshot(run_dir, snapshot)
    return run_dir, snapshot, visit, flow


def test_implementation_flow_shape_record_allow_cli() -> None:
    _, flow = load_registry(BUNDLE)
    record = next(node for node in flow["nodes"] if node.get("id") == NODE_SHAPE_RECORD)
    assert record["allow"]["cli"] == ["run.agent.submit", "visit.record.complete"]
    assert "worker" not in record


def test_record_complete_happy_path(tmp_path: Path) -> None:
    run_dir, snapshot, visit, flow = _record_opened_run(tmp_path)
    workspace = tmp_path / "app"
    result = run_shape_record_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is True
    assert result["next_node_id"] == "shape.record.gate"
    plan = run_dir / "artifacts" / str(visit["id"]) / "plan.md"
    assert plan.is_file()
    assert (workspace / "plan.md").is_file()


def test_record_complete_judgment_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "record-missing"
    run_dir.mkdir(parents=True)
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "record-missing",
        "status": "running",
        "visits": [],
        "ledger": [],
        "active_visit": {
            "id": "v-record",
            "node_id": NODE_SHAPE_RECORD,
            "kind": "step",
            "lifecycle": "opened",
        },
    }
    visit = snapshot["active_visit"]
    result = run_shape_record_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is False
    assert result["code"] == "JUDGMENT_MISSING"
