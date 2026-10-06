"""Unit tests for host execute.commit completion."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from foundry_cli.engine.execute_step_executor import run_execute_commit_complete
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.git_workspace import ensure_clean_git_workspace

BUNDLE = FOUNDRY_ROOT
NODE_EXECUTE_COMMIT = "execute.commit"


def _commit_opened_run(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    workspace = tmp_path / "app"
    workspace.mkdir()
    (workspace / "README.md").write_text("commit step test\n", encoding="utf-8")
    ensure_clean_git_workspace(workspace)
    subprocess.run(
        ["git", "checkout", "-b", "foundry/test"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )
    run_dir = workspace / ".foundry" / "runs" / "test-step"
    run_dir.mkdir(parents=True)
    (run_dir / "receipts").mkdir(exist_ok=True)
    visit_id = "v-commit"
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
            "node_id": NODE_EXECUTE_COMMIT,
            "kind": "step",
            "lifecycle": "opened",
        },
    }
    visit = snapshot["active_visit"]
    _, flow = load_registry(BUNDLE)
    return run_dir, snapshot, visit, flow


def test_implementation_flow_execute_commit_engine_owned() -> None:
    _, flow = load_registry(BUNDLE)
    commit_node = next(node for node in flow["nodes"] if node.get("id") == NODE_EXECUTE_COMMIT)
    assert "instructions" not in commit_node
    assert "worker" not in commit_node
    allow = commit_node.get("allow") or {}
    assert "cli" not in allow
    allow_state = allow.get("state") or []
    assert "final_commit_sha" in allow_state
    assert "execute_commit_message" in allow_state
    artifacts = commit_node.get("produces", {}).get("artifacts") or []
    assert any(a.get("id") == "final-commit" for a in artifacts)


def test_commit_complete_happy_path_stub(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    run_dir, snapshot, visit, flow = _commit_opened_run(tmp_path)
    workspace = tmp_path / "app"
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
    run_dir, snapshot, visit, flow = _commit_opened_run(tmp_path)
    workspace = tmp_path / "app"
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
