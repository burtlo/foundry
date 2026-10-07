"""Unit tests for engine mechanism runner skeleton (Step 5)."""

from __future__ import annotations

from pathlib import Path

import yaml

from foundry_cli.engine.actions import default_action_registry
from foundry_cli.engine.mechanism_runner import MechanismRunner


def _write_operations(bundle: Path, node_id: str, mechanism: list[dict[str, object]]) -> str:
    ops_path = bundle / "nodes" / node_id / "operations.yaml"
    ops_path.parent.mkdir(parents=True, exist_ok=True)
    ops_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "node_id": node_id,
                "mechanism": mechanism,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return f"registry:nodes/{node_id}/operations.yaml"


def test_default_registry_covers_step5_action_names() -> None:
    registry = default_action_registry()
    for action in (
        "visit.intake.complete",
        "visit.execute.branch.complete",
        "visit.execute.build.complete",
        "visit.execute.test.complete",
        "visit.execute.commit.complete",
        "execute.build.boundary.park",
        "receipt.seal",
        "artifact.publish",
        "visit.transition",
        "subprocess",
        "visit.state_patch",
        "run.advance.park",
    ):
        assert registry.has(action), f"missing action registration: {action}"


def test_runner_executes_mechanism_steps_in_order(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    operations_ref = _write_operations(
        bundle,
        "demo.node",
        [
            {
                "id": "set_feature_branch",
                "action": "visit.state_patch",
                "set": {"feature_branch": "feature/demo"},
            },
            {
                "id": "skip_without_sha",
                "action": "subprocess",
                "when": "state.final_commit_sha != null",
                "commands": [{"command": "echo skipped", "exit_code": 0}],
            },
            {
                "id": "park",
                "action": "run.advance.park",
                "when": "state.feature_branch != null",
                "summary": "Paused at boundary",
            },
            {
                "id": "never_reached_after_wait",
                "action": "visit.state_patch",
                "set": {"after_wait": True},
            },
        ],
    )

    flow = {"nodes": [{"id": "demo.node", "kind": "step"}]}
    visit = {"id": "v-001", "node_id": "demo.node", "kind": "step", "lifecycle": "opened"}
    snapshot = {"status": "running", "state": {}, "ledger": [], "active_visit": visit, "visits": [visit]}

    result = MechanismRunner().run(
        snapshot,
        visit,
        flow,
        operations_ref=operations_ref,
        workspace=workspace,
        foundry_bundle=bundle,
        run_dir=run_dir,
    )

    assert result["ok"] is True
    assert result["status"] == "wait"
    assert result["wait"]["summary"] == "Paused at boundary"
    assert snapshot["state"]["feature_branch"] == "feature/demo"
    assert "after_wait" not in snapshot["state"]
    assert [step["id"] for step in result["steps"]] == ["set_feature_branch", "skip_without_sha", "park"]
    assert result["steps"][0]["executed"] is True
    assert result["steps"][1]["skipped"] is True
    assert result["steps"][2]["executed"] is True


def test_runner_reports_transitioned_outcome(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    operations_ref = _write_operations(
        bundle,
        "demo.transition",
        [
            {
                "id": "transition_now",
                "action": "visit.transition",
                "summary": "Step complete",
            }
        ],
    )

    flow = {"nodes": [{"id": "demo.transition", "kind": "step", "terminal": True}]}
    visit = {
        "id": "v-001",
        "node_id": "demo.transition",
        "kind": "step",
        "lifecycle": "opened",
        "outcome": None,
    }
    snapshot = {"status": "running", "state": {}, "ledger": [], "active_visit": visit, "visits": [visit]}

    result = MechanismRunner().run(
        snapshot,
        visit,
        flow,
        operations_ref=operations_ref,
        workspace=workspace,
        foundry_bundle=bundle,
        run_dir=run_dir,
    )

    assert result["ok"] is True
    assert result["status"] == "transitioned"
    assert result["transitioned"] is True
    assert any(event.get("type") == "visit.sealed" for event in snapshot.get("ledger", []))
