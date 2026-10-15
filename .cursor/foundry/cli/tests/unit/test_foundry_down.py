"""``foundry down`` orchestration (mocked host and bridge)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry import _format_result
from foundry_cli.readiness.formatting import format_down_human
from foundry_cli.up_commands import cmd_down
import foundry_cli.up_commands as up_commands
from tests.acceptance.helpers import CLI_ENTRY
from tests.conftest import FOUNDRY_ROOT, REPO_ROOT


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        FOUNDRY_ROOT / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    return workspace


def test_cmd_down_stops_host_then_bridge(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    bundle = FOUNDRY_ROOT
    args = argparse.Namespace(workspace=str(workspace), registry=str(bundle), json=True)

    with patch.object(up_commands, "host_is_running", return_value=True):
        with patch.object(up_commands, "bridge_is_running", return_value=True):
            with patch.object(up_commands, "cmd_host_stop") as host_stop:
                host_stop.return_value = {"ok": True, "stopped": True, "was_running": True}
                with patch.object(up_commands, "stop_bridge") as stop_bridge:
                    stop_bridge.return_value = {"ok": True, "stopped": True, "was_running": True}
                    result = cmd_down(args)

    assert result.get("ok") is True
    assert result.get("already_stopped") is False
    assert "host" in (result.get("message") or "").lower()
    host_stop.assert_called_once_with(args)
    stop_bridge.assert_called_once_with(workspace.resolve())
    host = result.get("host")
    bridge = result.get("bridge")
    assert isinstance(host, dict) and host.get("was_running") is True
    assert isinstance(bridge, dict) and bridge.get("was_running") is True


def test_cmd_down_idempotent_when_already_stopped(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    args = argparse.Namespace(workspace=str(workspace), registry=str(FOUNDRY_ROOT), json=True)

    with patch.object(up_commands, "host_is_running", return_value=False):
        with patch.object(up_commands, "bridge_is_running", return_value=False):
            with patch.object(up_commands, "cmd_host_stop") as host_stop:
                with patch.object(up_commands, "stop_bridge") as stop_bridge:
                    result = cmd_down(args)

    assert result.get("ok") is True
    assert result.get("already_stopped") is True
    assert "already stopped" in (result.get("message") or "").lower()
    host_stop.assert_not_called()
    stop_bridge.assert_not_called()


def test_cmd_down_second_invocation_message(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    args = argparse.Namespace(workspace=str(workspace), registry=str(FOUNDRY_ROOT), json=True)

    with patch.object(up_commands, "host_is_running", side_effect=[True, False]):
        with patch.object(up_commands, "bridge_is_running", side_effect=[True, False]):
            with patch.object(up_commands, "cmd_host_stop") as host_stop:
                host_stop.return_value = {"ok": True, "stopped": True, "was_running": True}
                with patch.object(up_commands, "stop_bridge") as stop_bridge:
                    stop_bridge.return_value = {"ok": True, "stopped": True, "was_running": True}
                    first = cmd_down(args)
                    second = cmd_down(args)

    assert first.get("ok") is True and first.get("already_stopped") is False
    assert second.get("ok") is True and second.get("already_stopped") is True
    assert "already stopped" in (second.get("message") or "").lower()


def test_format_down_human_already_stopped(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(command="down", json=False)
    format_down_human(
        args,
        {
            "ok": True,
            "already_stopped": True,
            "message": "Foundry is already stopped for this workspace.",
            "workspace": "/tmp/ws",
        },
    )
    out = capsys.readouterr().out
    assert "already stopped" in out.lower()
    assert "workspace: /tmp/ws" in out
    assert "Next: foundry up" in out


def test_format_result_down_json_ok(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(command="down", json=True)
    payload = {
        "ok": True,
        "already_stopped": False,
        "message": "Stopped host and judgment bridge for this workspace.",
        "workspace": "/tmp/ws",
    }
    _format_result(args, payload)
    captured = capsys.readouterr().out
    parsed = json.loads(captured)
    assert parsed.get("ok") is True
    assert "error" not in parsed


def test_cli_down_json_dispatch(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI_ENTRY),
            "--workspace",
            str(workspace),
            "--registry",
            str(FOUNDRY_ROOT),
            "--json",
            "down",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload.get("ok") is True
    assert payload.get("already_stopped") is True
    assert "error" not in payload
