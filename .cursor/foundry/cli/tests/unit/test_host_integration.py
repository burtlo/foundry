"""Integration tests: host subprocess survives CLI detach."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from tests.conftest import FOUNDRY_ROOT
from tests.unit.git_workspace import ensure_clean_git_workspace, init_clean_git_repo

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    init_clean_git_repo(workspace)
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


def test_host_start_is_idempotent_when_already_running(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    host_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "foundry_cli.host",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
        ],
        cwd=str(BUNDLE / "cli"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            if json.loads(_run_cli(workspace, "host", "status").stdout).get("running"):
                break
            time.sleep(0.1)
        first = _run_cli(workspace, "host", "start")
        assert first.returncode == 0, first.stderr
        body = json.loads(first.stdout)
        assert body.get("already_running") is True
        second = _run_cli(workspace, "host", "start")
        assert second.returncode == 0, second.stderr
        assert json.loads(second.stdout).get("already_running") is True
    finally:
        stop = _run_cli(workspace, "host", "stop")
        if stop.returncode != 0:
            host_proc.terminate()
        host_proc.wait(timeout=15)


def _park_fixture_at_execute_start(workspace: Path, fixture_name: str) -> str:
    src = BUNDLE / "fixtures" / "runs" / fixture_name
    snapshot = json.loads((src / "snapshot.json").read_text(encoding="utf-8"))
    run_id = str(snapshot.get("run_id") or fixture_name)
    dest = workspace / ".foundry" / "runs" / run_id
    shutil.copytree(src, dest)
    decide = _run_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
    assert decide.returncode == 0, decide.stderr + decide.stdout
    advance = _run_cli(workspace, "run", "advance", "--run", run_id)
    assert advance.returncode == 0, advance.stderr + advance.stdout
    body = json.loads(advance.stdout)
    assert body.get("active_node_id") == "execute.start"
    assert body.get("wait", {}).get("kind") == "decision"
    ensure_clean_git_workspace(workspace)
    return run_id


def test_host_start_reaches_execute_intake_for_host_advance(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    host_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "foundry_cli.host",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
        ],
        cwd=str(BUNDLE / "cli"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            if json.loads(_run_cli(workspace, "host", "status").stdout).get("running"):
                break
            time.sleep(0.1)

        run_id = _park_fixture_at_execute_start(workspace, "porcelain-0007-v007-record-gate")
        ensure_clean_git_workspace(workspace)
        start = _run_cli(workspace, "start", run_id)
        assert start.returncode == 0, start.stderr + start.stdout
        body = json.loads(start.stdout)
        assert body.get("authorization_recorded") is True
        assert body.get("active_node_id") in {"execute.intake", "execute.plan", "execute.build"}
    finally:
        stop = _run_cli(workspace, "host", "stop")
        if stop.returncode != 0:
            host_proc.terminate()
        host_proc.wait(timeout=15)


def test_host_survives_cli_detach_and_run_get(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    host_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "foundry_cli.host",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
        ],
        cwd=str(BUNDLE / "cli"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        status = None
        for _ in range(50):
            status = _run_cli(workspace, "host", "status")
            if status.returncode == 0:
                body = json.loads(status.stdout)
                if body.get("running"):
                    break
            time.sleep(0.1)
        assert status is not None and status.returncode == 0
        assert json.loads(status.stdout).get("running") is True

        create = _run_cli(
            workspace,
            "run",
            "create",
            "--work-prompt",
            "Host integration proof",
        )
        assert create.returncode == 0, create.stderr
        run_id = json.loads(create.stdout)["run_id"]

        advance = _run_cli(workspace, "run", "advance", "--run", run_id)
        assert advance.returncode == 0, advance.stderr

        get_first = _run_cli(workspace, "run", "get", "--run", run_id)
        assert get_first.returncode == 0, get_first.stderr
        first_body = json.loads(get_first.stdout)
        assert first_body.get("run_id") == run_id
        revision = first_body.get("revision")

        get_second = _run_cli(workspace, "run", "get", "--run", run_id)
        assert get_second.returncode == 0, get_second.stderr
        second_body = json.loads(get_second.stdout)
        assert second_body.get("revision") == revision
        assert second_body.get("active_node_id") == "shape.present.gate"
        wait = second_body.get("wait")
        assert isinstance(wait, dict)
        assert wait.get("kind") == "decision"

        health = _run_cli(workspace, "host", "status")
        assert json.loads(health.stdout).get("running") is True
    finally:
        stop = _run_cli(workspace, "host", "stop")
        if stop.returncode != 0:
            host_proc.terminate()
        host_proc.wait(timeout=15)
