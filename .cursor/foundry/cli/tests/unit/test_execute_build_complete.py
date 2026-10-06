"""Unit tests for host execute.build completion."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.engine.execute_step_executor import run_execute_build_complete
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT
NODE_EXECUTE_BUILD = "execute.build"


def _build_opened_run(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    workspace = tmp_path / "app"
    workspace.mkdir()
    run_dir = workspace / ".foundry" / "runs" / "build-test"
    run_dir.mkdir(parents=True)
    (run_dir / "receipts").mkdir(exist_ok=True)
    visit_id = "v-build"
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "build-test",
        "status": "running",
        "flow_id": "implementation",
        "state": {
            "execution_graph_id": "build-test:execution-graph",
            "feature_branch": "foundry/test",
            "approved_ac": "Ship it.",
        },
        "visits": [],
        "ledger": [],
        "active_visit": {
            "id": visit_id,
            "node_id": NODE_EXECUTE_BUILD,
            "kind": "step",
            "lifecycle": "opened",
        },
    }
    visit = snapshot["active_visit"]
    _, flow = load_registry(BUNDLE)
    return run_dir, snapshot, visit, flow


def test_implementation_flow_execute_build_engine_owned() -> None:
    _, flow = load_registry(BUNDLE)
    build_node = next(node for node in flow["nodes"] if node.get("id") == NODE_EXECUTE_BUILD)
    assert "instructions" not in build_node
    assert "worker" not in build_node
    assert build_node.get("allow", {}).get("state") == ["last_build_exit_code"]
    assert "files" not in build_node.get("allow", {})


def test_build_complete_happy_path_stub(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    run_dir, snapshot, visit, flow = _build_opened_run(tmp_path)
    workspace = tmp_path / "app"
    result = run_execute_build_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is True
    assert result.get("next_node_id") == "execute.test"
    assert snapshot.get("state", {}).get("last_build_exit_code") == 0
    agent_path = run_dir / "receipts" / "agent.json"
    assert agent_path.is_file()
    draft = json.loads(agent_path.read_text(encoding="utf-8"))
    assert draft.get("agent", {}).get("name") == "feature-builder"
    assert draft.get("status") == "completed"
    commands = draft.get("commands") or []
    assert commands and commands[0].get("exit_code") == 0


def test_build_complete_records_failed_stub_exit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    monkeypatch.setenv("FOUNDRY_EXECUTE_BUILD_EXIT_CODE", "2")
    run_dir, snapshot, visit, flow = _build_opened_run(tmp_path)
    workspace = tmp_path / "app"
    result = run_execute_build_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is False
    assert result.get("reopened") is True
    assert result.get("code") == "CHECK_FAILED"
    agent_path = run_dir / "receipts" / "agent.json"
    draft = json.loads(agent_path.read_text(encoding="utf-8"))
    assert draft.get("status") == "failed"
    assert snapshot.get("state", {}).get("last_build_exit_code") == 2
