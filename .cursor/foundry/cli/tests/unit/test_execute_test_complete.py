"""Unit tests for host execute.test completion."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.engine.execute_step_executor import run_execute_test_complete
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.execute_step_fixtures import assert_execute_step_engine_owned, opened_execute_step_run

BUNDLE = FOUNDRY_ROOT
NODE_EXECUTE_TEST = "execute.test"


def test_implementation_flow_execute_test_engine_owned() -> None:
    _, flow = load_registry(BUNDLE)
    assert_execute_step_engine_owned(
        flow,
        NODE_EXECUTE_TEST,
        allow_state_contains=("last_test_exit_code", "repair_loop_count"),
    )


def test_test_complete_happy_path_stub(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    workspace, run_dir, snapshot, visit, flow = opened_execute_step_run(
        tmp_path,
        node_id=NODE_EXECUTE_TEST,
        run_id="test-step",
        visit_id="v-test",
        state={
            "execution_graph_id": "test-step:execution-graph",
            "feature_branch": "foundry/test",
        },
    )
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
    workspace, run_dir, snapshot, visit, flow = opened_execute_step_run(
        tmp_path,
        node_id=NODE_EXECUTE_TEST,
        run_id="test-step",
        visit_id="v-test",
        state={
            "execution_graph_id": "test-step:execution-graph",
            "feature_branch": "foundry/test",
        },
    )
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
