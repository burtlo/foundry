"""Unit tests for visit present complete executor."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from foundry_cli.engine.shape_step_executor import run_shape_present_complete
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import NODE_SHAPE_PRESENT
from tests.unit.shape_flow_helpers import present_opened_run, shape_test_workspace

BUNDLE = FOUNDRY_ROOT


def test_implementation_flow_shape_present_allow_cli() -> None:
    _, flow = load_registry(BUNDLE)
    present = next(node for node in flow["nodes"] if node.get("id") == NODE_SHAPE_PRESENT)
    assert present["allow"]["cli"] == ["run.agent.submit", "visit.present.complete"]
    assert "worker" not in present
    assert "questions_asked_total" not in (present.get("reads", {}).get("state") or [])


def test_present_complete_happy_path(tmp_path: Path) -> None:
    run_dir, snapshot, visit, flow = present_opened_run(tmp_path)
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
    workspace = shape_test_workspace(tmp_path)
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
