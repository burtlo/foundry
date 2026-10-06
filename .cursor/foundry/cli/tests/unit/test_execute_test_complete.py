"""Unit tests for host execute.test completion."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.engine.execute_step_executor import run_execute_test_complete
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT
NODE_EXECUTE_TEST = "execute.test"


def _test_opened_run(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    workspace = tmp_path / "app"
    workspace.mkdir()
    run_dir = workspace / ".foundry" / "runs" / "test-step"
    run_dir.mkdir(parents=True)
    (run_dir / "receipts").mkdir(exist_ok=True)
    visit_id = "v-test"
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "test-step",
        "status": "running",
        "flow_id": "implementation",
        "state": {
            "execution_graph_id": "test-step:execution-graph",
            "feature_branch": "foundry/test",
        },
        "visits": [],
        "ledger": [],
        "active_visit": {
            "id": visit_id,
            "node_id": NODE_EXECUTE_TEST,
            "kind": "step",
            "lifecycle": "opened",
        },
    }
    visit = snapshot["active_visit"]
    _, flow = load_registry(BUNDLE)
    return run_dir, snapshot, visit, flow


def test_implementation_flow_execute_test_engine_owned() -> None:
    _, flow = load_registry(BUNDLE)
    test_node = next(node for node in flow["nodes"] if node.get("id") == NODE_EXECUTE_TEST)
    assert "instructions" not in test_node
    assert "worker" not in test_node
    allow_state = test_node.get("allow", {}).get("state") or []
    assert "last_test_exit_code" in allow_state
    assert "repair_loop_count" in allow_state
    assert "files" not in test_node.get("allow", {})


def test_test_complete_happy_path_stub(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    run_dir, snapshot, visit, flow = _test_opened_run(tmp_path)
    workspace = tmp_path / "app"
    result = run_execute_test_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is True
    assert result.get("next_node_id") == "execute.test.gate"
    assert snapshot.get("state", {}).get("last_test_exit_code") == 0
    agent_path = run_dir / "receipts" / "agent.json"
    assert agent_path.is_file()
    draft = json.loads(agent_path.read_text(encoding="utf-8"))
    assert draft.get("agent", {}).get("name") == "repairer"
    assert draft.get("status") == "completed"
    commands = draft.get("commands") or []
    assert commands and commands[0].get("exit_code") == 0
    outputs = draft.get("outputs") or {}
    assert outputs.get("verification_policy") == "implementation"


def test_test_complete_records_failed_stub_exit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    monkeypatch.setenv("FOUNDRY_EXECUTE_TEST_EXIT_CODE", "1")
    run_dir, snapshot, visit, flow = _test_opened_run(tmp_path)
    workspace = tmp_path / "app"
    result = run_execute_test_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is True
    assert result.get("next_node_id") == "execute.test.gate"
    assert snapshot.get("state", {}).get("last_test_exit_code") == 1
    agent_path = run_dir / "receipts" / "agent.json"
    draft = json.loads(agent_path.read_text(encoding="utf-8"))
    assert draft.get("status") == "failed"
