"""Unit tests for visit record complete executor."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.shape_step_executor import run_shape_record_complete
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import NODE_SHAPE_RECORD
from tests.unit.shape_flow_helpers import record_opened_run, shape_test_workspace

BUNDLE = FOUNDRY_ROOT


def test_implementation_flow_shape_record_allow_cli() -> None:
    _, flow = load_registry(BUNDLE)
    record = next(node for node in flow["nodes"] if node.get("id") == NODE_SHAPE_RECORD)
    assert record["allow"]["cli"] == ["run.agent.submit", "visit.record.complete"]
    assert "worker" not in record


def test_record_complete_happy_path(tmp_path: Path) -> None:
    run_dir, snapshot, visit, flow = record_opened_run(tmp_path)
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
    workspace = shape_test_workspace(tmp_path)
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
