"""Unit tests for visit examine complete executor."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.lifecycle import admit_visit
from foundry_cli.engine.shape_step_executor import run_shape_examine_complete
from foundry_cli.registry import load_registry
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import NODE_SHAPE_EXAMINE, NODE_SHAPE_INTAKE
from tests.unit.test_advance import _intake_open_run
from tests.unit.test_agent_connection import _valid_result
from foundry_cli.engine.agent.submit import submit_agent_result

BUNDLE = FOUNDRY_ROOT


def _examine_opened_run(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Examine complete tests")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    visit = snapshot["active_visit"]
    assert visit["node_id"] == NODE_SHAPE_EXAMINE
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
    save_snapshot(run_dir, snapshot)
    return run_dir, snapshot, visit, flow


def test_implementation_flow_shape_examine_allow_cli() -> None:
    _, flow = load_registry(BUNDLE)
    examine = next(node for node in flow["nodes"] if node.get("id") == NODE_SHAPE_EXAMINE)
    assert examine["allow"]["cli"] == ["run.agent.submit", "visit.examine.complete"]
    assert "operations" not in examine
    assert examine.get("allow", {}).get("user", {}).get("ask") is not True


def test_examine_complete_fast_lane(tmp_path: Path) -> None:
    run_dir, snapshot, visit, flow = _examine_opened_run(tmp_path)
    workspace = Path(snapshot["workspace"])
    result = run_shape_examine_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is True
    assert result["next_node_id"] == "shape.present"
    agent = json.loads((run_dir / "receipts" / "agent.json").read_text(encoding="utf-8"))
    assert agent["recommended_next_state"] == "shape.present"


def test_examine_complete_gate_path(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "gate-0001"
    run_dir.mkdir(parents=True)
    (run_dir / "artifacts").mkdir()
    (run_dir / "receipts").mkdir()
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "gate-0001",
        "run_uuid": "00000000-0000-4000-8000-000000000088",
        "flow_id": "implementation",
        "status": "running",
        "workspace": str(workspace),
        "config": {"workspace": str(workspace), "shape": {"work_prompt": "Gate path"}},
        "state": {"ticket": None, "app_folder": None},
        "visits": [],
        "ledger": [],
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
    advance_run(snapshot, flow, workspace=workspace, foundry_bundle=BUNDLE, run_dir=run_dir)
    visit = snapshot["active_visit"]
    advance_run(snapshot, flow, workspace=workspace, foundry_bundle=BUNDLE, run_dir=run_dir)
    wait = snapshot["wait"]
    submit_agent_result(
        snapshot,
        request_id=str(wait["request_ref"]),
        result=_valid_result(
            questions=[{"id": "q1", "text": "Scope?", "why_needed": "AC"}],
        ),
        foundry_bundle=BUNDLE,
    )
    result = run_shape_examine_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        with_open_questions=True,
    )
    assert result["ok"] is True
    assert result["next_node_id"] == "shape.examine.gate"
    agent = json.loads((run_dir / "receipts" / "agent.json").read_text(encoding="utf-8"))
    assert agent["recommended_next_state"] == "shape.examine.gate"


def test_examine_complete_rejects_open_questions_without_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Open questions block complete")
    advance_run(snapshot, flow, workspace=workspace, foundry_bundle=BUNDLE, run_dir=run_dir)
    visit = snapshot["active_visit"]
    advance_run(snapshot, flow, workspace=workspace, foundry_bundle=BUNDLE, run_dir=run_dir)
    wait = snapshot["wait"]
    submit_agent_result(
        snapshot,
        request_id=str(wait["request_ref"]),
        result=_valid_result(
            questions=[{"id": "q1", "text": "Scope?", "why_needed": "AC"}],
        ),
        foundry_bundle=BUNDLE,
    )
    outcome = run_shape_examine_complete(
        snapshot,
        visit,
        flow,
        workspace=Path(snapshot["workspace"]),
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert outcome["ok"] is False
    assert outcome["code"] == "OPEN_QUESTIONS_PENDING"


def test_examine_complete_rejects_counter_mismatch(tmp_path: Path) -> None:
    run_dir, snapshot, visit, flow = _examine_opened_run(tmp_path)
    state = snapshot["state"]
    state["clarifying_questions"] = [
        {"id": "q1", "text": "Scope?", "why_needed": "AC", "status": "open"},
    ]
    state["open_clarifying_questions_count"] = 0
    outcome = run_shape_examine_complete(
        snapshot,
        visit,
        flow,
        workspace=Path(snapshot["workspace"]),
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert outcome["ok"] is False
    assert outcome["code"] == "OPEN_QUESTIONS_MISMATCH"


def test_advance_auto_completes_examine_to_present(tmp_path: Path) -> None:
    run_dir, snapshot, _visit, flow = _examine_opened_run(tmp_path)
    workspace = Path(snapshot["workspace"])
    assert snapshot.get("wait") is None
    result = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=1,
    )
    assert result["steps_taken"] == 1
    assert result["reason"] == "examine_complete"
    assert snapshot["active_visit"]["node_id"] == "shape.present"
