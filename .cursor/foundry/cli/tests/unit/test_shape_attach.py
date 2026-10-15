"""Unit tests for ``foundry shape --attach`` (P8)."""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_cli.command_context import CommandContext
from foundry_cli.engine.agent.adapter import StubAgentAdapter, default_stub_examination_result
from foundry_cli.run_service import advance_run_durable, create_run
from foundry_cli.run_store import get_revision, load_snapshot
from foundry_cli.user_cli import stream_run_attach
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import shape_test_workspace

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"


def _args_namespace(workspace: Path) -> argparse.Namespace:
    return argparse.Namespace(
        workspace=str(workspace),
        registry=str(BUNDLE),
        json=False,
        local=True,
        no_host=True,
        no_follow=False,
    )


def _advance_run_with_questions(workspace: Path, run_id: str) -> None:
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
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


def _wait_for_run_id(workspace: Path, timeout: float = 10.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        runs_root = workspace / ".foundry" / "runs"
        if runs_root.is_dir():
            for child in sorted(runs_root.iterdir()):
                if child.is_dir():
                    return child.name
        time.sleep(0.05)
    raise AssertionError("timed out waiting for run directory")


def _popen_shape_attach(workspace: Path, prompt: str) -> subprocess.Popen[str]:
    kwargs: dict = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(
        [
            sys.executable,
            str(CLI),
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            "shape",
            "--input",
            prompt,
            "--no-host",
            "--attach",
        ],
        **kwargs,
    )


def _interrupt_proc(proc: subprocess.Popen[str]) -> None:
    if sys.platform == "win32":
        proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        proc.send_signal(signal.SIGINT)


def test_shape_attach_wires_human_stream_after_intake(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Intake handoff prints first; attach stream uses human question formatting."""
    import foundry as foundry_cli_main

    workspace = shape_test_workspace(tmp_path)
    stream_calls: list[bool] = []

    def fake_stream(ctx, stream_args, *, run_id, human_questions=False, after_seq=0):
        stream_calls.append(human_questions)
        return {"ok": True, "detached": True, "run_id": run_id, "after_seq": after_seq}

    with patch("foundry.stream_run_attach", side_effect=fake_stream):
        exit_code = foundry_cli_main.main(
            [
                "--workspace",
                str(workspace),
                "--registry",
                str(BUNDLE),
                "shape",
                "--input",
                "Shape attach wiring",
                "--no-host",
                "--attach",
            ]
        )

    assert exit_code == 0
    assert stream_calls == [True]
    out = capsys.readouterr().out
    assert "Shape request received." in out
    assert "Intake successful." in out
    assert "foundry attach" in out


def test_shape_attach_streams_questions_after_examine(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    created = create_run(workspace=workspace, bundle=BUNDLE, work_prompt="Stream questions")
    run_id = str(created["run_id"])
    _advance_run_with_questions(workspace, run_id)

    ctx = CommandContext(workspace=workspace, bundle=BUNDLE)
    args = _args_namespace(workspace)
    ticks = 0

    def sleep_side_effect(_seconds: float) -> None:
        nonlocal ticks
        ticks += 1
        if ticks >= 2:
            raise KeyboardInterrupt

    with patch("foundry_cli.user_cli.time.sleep", side_effect=sleep_side_effect):
        result = stream_run_attach(ctx, args, run_id=run_id, human_questions=True)

    assert result.get("ok") is True
    assert result.get("detached") is True


def test_shape_attach_streams_questions_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = shape_test_workspace(tmp_path)
    created = create_run(workspace=workspace, bundle=BUNDLE, work_prompt="Stderr questions")
    run_id = str(created["run_id"])
    _advance_run_with_questions(workspace, run_id)

    ctx = CommandContext(workspace=workspace, bundle=BUNDLE)
    args = _args_namespace(workspace)

    with patch("foundry_cli.user_cli.time.sleep", side_effect=KeyboardInterrupt):
        stream_run_attach(ctx, args, run_id=run_id, human_questions=True)

    err = capsys.readouterr().err
    assert "question q1: Which API?" in err
    assert "detached (run continues)" in err


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT detach exit code differs on Windows")
def test_shape_attach_streams_until_detach(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    proc = _popen_shape_attach(workspace, "Detach after intake")

    time.sleep(0.8)
    _interrupt_proc(proc)
    stdout, stderr = proc.communicate(timeout=15)

    assert proc.returncode == 0, stderr + stdout
    assert "Shape request received." in stdout
    assert "Intake successful." in stdout
    assert "detached (run continues)" in stderr
    run_id = _wait_for_run_id(workspace, timeout=2.0)
    snapshot = load_snapshot(workspace / ".foundry" / "runs" / run_id)
    assert snapshot.get("status") == "running"


def test_shape_attach_json_skips_stream(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--json",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            "shape",
            "--input",
            "Json attach",
            "--no-host",
            "--attach",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body.get("ok") is True
    assert body.get("intake_complete") is True
    assert "event_type" not in result.stdout


def test_stream_run_attach_detach_without_human_format(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = shape_test_workspace(tmp_path)
    created = create_run(workspace=workspace, bundle=BUNDLE, work_prompt="Detach test")
    run_id = str(created["run_id"])
    ctx = CommandContext(workspace=workspace, bundle=BUNDLE)
    args = _args_namespace(workspace)

    with patch("foundry_cli.user_cli.time.sleep", side_effect=KeyboardInterrupt):
        result = stream_run_attach(ctx, args, run_id=run_id, human_questions=False)

    assert result.get("ok") is True
    assert result.get("detached") is True
    err = capsys.readouterr().err
    assert "detached (run continues)" in err
    assert "question q1:" not in err


@pytest.mark.skipif(sys.platform == "win32", reason="CTRL_BREAK subprocess stdout is unreliable on Windows")
def test_shape_attach_intake_stdout_subprocess(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    proc = _popen_shape_attach(workspace, "Intake stdout check")

    def detach_soon() -> None:
        time.sleep(1.2)
        _interrupt_proc(proc)

    threading.Thread(target=detach_soon, daemon=True).start()
    stdout, stderr = proc.communicate(timeout=20)
    combined = stdout + stderr
    assert "Shape request received." in stdout
    assert "Intake successful." in stdout
    assert "run=" in combined
    assert "detached (run continues)" in stderr
