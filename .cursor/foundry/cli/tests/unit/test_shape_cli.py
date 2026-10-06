"""Unit tests for Phase 5 user Shape CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import NODE_SHAPE_EXAMINE

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    return workspace


def _run_cli(workspace: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--json",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            *argv,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_shape_creates_run_and_reaches_operator_wait(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    prompt = "Add rate limiting to the API"
    result = _run_cli(
        workspace,
        "shape",
        "--input",
        prompt,
        "--no-host",
    )
    assert result.returncode == 0, result.stderr + result.stdout
    body = json.loads(result.stdout)
    assert body.get("ok") is True
    run_id = body["run_id"]
    assert body.get("active_node_id") == NODE_SHAPE_EXAMINE
    wait = body.get("wait")
    assert isinstance(wait, dict)
    assert wait.get("kind") == "operator"
    assert body.get("work_prompt") == prompt

    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    config = snapshot.get("config")
    assert isinstance(config, dict)
    shape_cfg = config.get("shape")
    assert isinstance(shape_cfg, dict)
    assert shape_cfg.get("work_prompt") == prompt


def test_answer_clears_user_input_wait(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    from foundry_cli.engine.agent.adapter import StubAgentAdapter, default_stub_examination_result
    from foundry_cli.run_service import advance_run_durable
    from foundry_cli.run_store import get_revision, save_snapshot
    from tests.unit.test_advance import _intake_open_run

    run_dir, snapshot, _flow = _intake_open_run(workspace, work_prompt="Answer me")
    save_snapshot(run_dir, snapshot)
    result = default_stub_examination_result()
    result = dict(result)
    result["questions"] = [{"id": "q1", "text": "Which API?", "why_needed": "Scope"}]
    stub = StubAgentAdapter(default_result=result)
    advance_run_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_dir=run_dir,
        expected_revision=get_revision(snapshot),
        agent_adapter=stub,
    )
    run_id = snapshot["run_id"]
    answer = _run_cli(
        workspace,
        "answer",
        run_id,
        "--answers",
        '{"q1": "REST v2"}',
        "--local",
    )
    assert answer.returncode == 0, answer.stderr + answer.stdout
    body = json.loads(answer.stdout)
    assert body.get("ok") is True
    assert body.get("wait") is None
    final = load_snapshot(run_dir)
    assert final["state"]["clarifying_answers"]["q1"] == "REST v2"


def test_decide_wait_kind_mismatch_after_examination(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    shape = _run_cli(workspace, "shape", "--input", "Need decisions", "--no-host")
    assert shape.returncode == 0, shape.stderr
    run_id = json.loads(shape.stdout)["run_id"]

    decide = _run_cli(workspace, "decide", run_id, "accept", "--local")
    assert decide.returncode != 0
    body = json.loads(decide.stdout)
    assert body.get("ok") is False
    assert body.get("error", {}).get("code") == "WAIT_KIND_MISMATCH"


def test_parse_request_accepts_run_answer() -> None:
    from foundry_cli.host.protocol import parse_request_line

    payload = {
        "protocol_version": 1,
        "id": "req-answer",
        "method": "run.answer",
        "params": {
            "idempotency_key": "answer-key",
            "expected_revision": 4,
            "run_id": "adv-0001",
            "answers": {"q1": "REST"},
        },
    }
    parsed = parse_request_line(json.dumps(payload))
    assert parsed["method"] == "run.answer"


def test_parse_request_accepts_run_create() -> None:
    from foundry_cli.host.protocol import parse_request_line

    payload = {
        "protocol_version": 1,
        "id": "req-create",
        "method": "run.create",
        "params": {
            "idempotency_key": "create-key",
            "work_prompt": "Hello shape",
        },
    }
    parsed = parse_request_line(json.dumps(payload))
    assert parsed["method"] == "run.create"


def test_start_requires_execute_start_gate(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    shape = _run_cli(workspace, "shape", "--input", "Not execute yet", "--no-host")
    assert shape.returncode == 0, shape.stderr
    run_id = json.loads(shape.stdout)["run_id"]
    result = _run_cli(workspace, "start", run_id, "--no-host")
    assert result.returncode != 0
    body = json.loads(result.stdout)
    assert body.get("error", {}).get("code") == "EXECUTE_START_GATE_REQUIRED"
