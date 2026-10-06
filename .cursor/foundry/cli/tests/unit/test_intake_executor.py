"""Unit tests for deterministic shape.intake executor."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from foundry_cli.engine.intake_executor import BLOCK_REASON_MISSING_WORK_PROMPT, run_shape_intake_complete
from foundry_cli.engine.lifecycle import admit_visit
from foundry_cli.registry import load_registry  # used by intake_run fixture and flow contract test
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import NODE_SHAPE_INTAKE

BUNDLE = FOUNDRY_ROOT


def test_implementation_flow_shape_intake_omits_instructions() -> None:
    _, flow = load_registry(BUNDLE)
    intake = next(node for node in flow["nodes"] if node.get("id") == NODE_SHAPE_INTAKE)
    assert "instructions" not in intake
    assert intake["allow"]["cli"] == ["visit.intake.complete", "visit.state_patch"]


@pytest.fixture
def intake_run(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )

    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "test-0001"
    run_dir.mkdir(parents=True)
    (run_dir / "artifacts").mkdir()
    (run_dir / "receipts").mkdir()

    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "test-0001",
        "run_uuid": "00000000-0000-4000-8000-000000000001",
        "flow_id": "implementation",
        "status": "running",
        "workspace": str(workspace),
        "config": {"workspace": str(workspace)},
        "state": {"ticket": None, "app_folder": None},
        "visits": [],
        "ledger": [],
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
    return run_dir, snapshot, visit, flow


def test_intake_complete_passes_and_transitions(intake_run) -> None:
    run_dir, snapshot, visit, flow = intake_run
    workspace = Path(snapshot["workspace"])
    result = run_shape_intake_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        work_prompt="Ship feature X",
    )
    assert result["ok"] is True
    assert result["intake_status"] == "passed"
    assert result["next_node_id"] == "shape.examine"
    ticket = json.loads((run_dir / "ticket.json").read_text(encoding="utf-8"))
    assert ticket["raw_input"] == "Ship feature X"
    assert ticket["normalized_translation"] is None


def test_intake_complete_blocked_without_work_prompt(intake_run) -> None:
    run_dir, snapshot, visit, flow = intake_run
    workspace = Path(snapshot["workspace"])
    result = run_shape_intake_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        work_prompt=None,
    )
    assert result["ok"] is True
    assert result["intake_status"] == "blocked"
    assert result["block_reason"] == BLOCK_REASON_MISSING_WORK_PROMPT
    assert result["transitioned"] is False
    assert not (run_dir / "ticket.json").exists()


def test_intake_rerun_after_blocked_passes(intake_run) -> None:
    run_dir, snapshot, visit, flow = intake_run
    workspace = Path(snapshot["workspace"])
    blocked = run_shape_intake_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        work_prompt=None,
    )
    assert blocked["intake_status"] == "blocked"
    snapshot["state"]["ticket"] = {"schema_version": "2.2.0", "raw_input": "stale"}
    passed = run_shape_intake_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        work_prompt="After block",
    )
    assert passed["ok"] is True
    assert passed["intake_status"] == "passed"
    assert snapshot["state"]["ticket"]["raw_input"] == "After block"


def test_intake_already_complete_denied(intake_run) -> None:
    run_dir, snapshot, visit, flow = intake_run
    workspace = Path(snapshot["workspace"])
    visit_id = str(visit["id"])
    from foundry_cli.constants import EVENT_ARTIFACT_LINKED
    from foundry_cli.ledger import append_event

    append_event(
        snapshot,
        event_type=EVENT_ARTIFACT_LINKED,
        visit_id=visit_id,
        node_id=NODE_SHAPE_INTAKE,
        payload={
            "artifact_id": "ticket",
            "uri": f"run:artifacts/{visit_id}/ticket.json",
            "schema": "registry:schemas/ticket.schema.json",
        },
    )
    (run_dir / "receipts" / "intake.json").write_text(
        json.dumps({"status": "passed"}),
        encoding="utf-8",
    )
    result = run_shape_intake_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        work_prompt="Twice",
    )
    assert result["ok"] is False
    assert result["code"] == "INTAKE_ALREADY_COMPLETE"
