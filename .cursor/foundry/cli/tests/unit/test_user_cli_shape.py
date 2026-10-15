"""Unit tests for user-facing Shape CLI commands (shape, answer, decide, status)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import intake_open_run, shape_test_workspace

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"


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


def test_shape_completes_intake_and_prints_handoff_hints(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
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
    assert body.get("intake_status") == "passed"
    assert body.get("intake_complete") is True
    assert body.get("attach_hint") == f"foundry attach {run_id}"
    assert body.get("status_hint") == f"foundry status {run_id}"
    assert body.get("work_prompt") == prompt
    wait = body.get("wait")
    assert wait is None or not isinstance(wait, dict) or wait.get("kind") != "decision"
    assert body.get("active_node_id") != "shape.present.gate"

    human = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            "shape",
            "--input",
            "Second shape for human output",
            "--no-host",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert human.returncode == 0, human.stderr + human.stdout
    out = human.stdout
    assert "Shape request received." in out
    assert "Intake successful." in out
    assert "run=" in out
    assert "foundry attach" in out
    assert "foundry status" in out

    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    config = snapshot.get("config")
    assert isinstance(config, dict)
    shape_cfg = config.get("shape")
    assert isinstance(shape_cfg, dict)
    assert shape_cfg.get("work_prompt") == prompt


def test_answer_clears_user_input_wait(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    from foundry_cli.engine.agent.adapter import StubAgentAdapter, default_stub_examination_result
    from foundry_cli.run_service import advance_run_durable
    from foundry_cli.run_store import get_revision, save_snapshot
    run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Answer me")
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
    wait = body.get("wait")
    assert isinstance(wait, dict)
    assert wait.get("kind") == "agent"
    final = load_snapshot(run_dir)
    assert final["state"]["clarifying_answers"]["q1"] == "REST v2"


def test_decide_wait_kind_mismatch_when_not_on_gate(tmp_path: Path) -> None:
    from foundry_cli.run_service import advance_run_durable

    workspace = shape_test_workspace(tmp_path)
    shape = _run_cli(workspace, "shape", "--input", "Need decisions", "--no-host")
    assert shape.returncode == 0, shape.stderr
    body = json.loads(shape.stdout)
    run_id = body["run_id"]
    advance_run_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_id=run_id,
        expected_revision=body["revision"],
        step_budget=8,
    )
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    assert snapshot.get("active_visit", {}).get("node_id") == "shape.present.gate"
    assert snapshot.get("wait", {}).get("kind") == "decision"

    status = _run_cli(workspace, "status", run_id, "--local")
    assert status.returncode == 0
    decide = _run_cli(workspace, "decide", run_id, "reject", "--local")
    assert decide.returncode == 0
    decide_body = json.loads(decide.stdout)
    assert decide_body.get("ok") is True

    mismatch = _run_cli(workspace, "answer", run_id, "--answers", '{"q1": "n/a"}', "--local")
    assert mismatch.returncode != 0
    err = json.loads(mismatch.stdout)
    assert err.get("error", {}).get("code") == "WAIT_KIND_MISMATCH"


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
    workspace = shape_test_workspace(tmp_path)
    shape = _run_cli(workspace, "shape", "--input", "Not execute yet", "--no-host")
    assert shape.returncode == 0, shape.stderr
    run_id = json.loads(shape.stdout)["run_id"]
    result = _run_cli(workspace, "start", run_id, "--no-host")
    assert result.returncode != 0
    body = json.loads(result.stdout)
    assert body.get("error", {}).get("code") == "EXECUTE_START_GATE_REQUIRED"
