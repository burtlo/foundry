"""Unit tests for host execute.commit completion."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.engine.execute_step_executor import run_execute_commit_complete
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.execute_step_fixtures import assert_execute_step_engine_owned, opened_execute_commit_run

BUNDLE = FOUNDRY_ROOT
NODE_EXECUTE_COMMIT = "execute.commit"


def test_implementation_flow_execute_commit_engine_owned() -> None:
    _, flow = load_registry(BUNDLE)
    assert_execute_step_engine_owned(
        flow,
        NODE_EXECUTE_COMMIT,
        forbid_cli=True,
        allow_state_contains=("final_commit_sha", "execute_commit_message"),
        artifact_id="final-commit",
    )


def test_commit_complete_happy_path_stub(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    workspace, run_dir, snapshot, visit, flow = opened_execute_commit_run(tmp_path)
    result = run_execute_commit_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is True
    assert result.get("next_node_id") == "execute.commit.gate"
    sha = snapshot.get("state", {}).get("final_commit_sha")
    assert isinstance(sha, str) and sha.strip()
    agent_path = run_dir / "receipts" / "agent.json"
    assert agent_path.is_file()
    draft = json.loads(agent_path.read_text(encoding="utf-8"))
    assert draft.get("agent", {}).get("name") == "commit-agent"
    assert draft.get("status") == "completed"
    outputs = draft.get("outputs") or {}
    assert outputs.get("final_commit_sha") == sha


def test_commit_complete_stub_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    monkeypatch.setenv("FOUNDRY_EXECUTE_COMMIT_EXIT_CODE", "1")
    workspace, run_dir, snapshot, visit, flow = opened_execute_commit_run(tmp_path)
    result = run_execute_commit_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result.get("ok") is False
    assert result.get("code") == "COMMIT_FAILED"
