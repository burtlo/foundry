"""``foundry up`` orchestration (mocked bridge)."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_cli.up_commands import cmd_up
import foundry_cli.up_commands as up_commands
from tests.conftest import FOUNDRY_ROOT


def test_cmd_up_ready_when_dimensions_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_CURSOR_API_KEY", "test-key")
    bundle = FOUNDRY_ROOT
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        bundle / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    fake_bridge = {
        "ok": True,
        "started": True,
        "bridge_url": "http://127.0.0.1:18791/v1/agent",
        "pid": 4242,
        "workspace": str(workspace),
        "health": {"ok": True},
    }
    args = argparse.Namespace(
        workspace=str(workspace),
        registry=str(bundle),
        json=True,
        foreground=False,
    )

    with patch("foundry_cli.up_commands.reconcile_bridge", return_value=fake_bridge):
        with patch("foundry_cli.up_commands.host_is_running", return_value=False):
            with patch("foundry_cli.up_commands.cmd_host_start") as start:
                start.return_value = {"ok": True, "started": True, "pid": 5252}
                with patch(
                    "foundry_cli.up_commands.host_process_dimension",
                    return_value={"ok": True, "pid": 5252},
                ):
                    with patch(
                        "foundry_cli.up_commands.host_health_dimension",
                        return_value={"ok": True},
                    ):
                        with patch(
                            "foundry_cli.up_commands.adapter_dimension",
                            return_value={
                                "ok": True,
                                "configured": True,
                                "reachable": True,
                            },
                        ):
                            with patch(
                                "foundry_cli.up_commands.bridge_readiness_from_url",
                                return_value={"ok": True, "url": fake_bridge["bridge_url"]},
                            ):
                                result = cmd_up(args)

    assert result.get("ok") is True
    assert result.get("ready") is True
    assert result.get("workspace") == str(workspace.resolve())


def test_cmd_up_foreground_shutdown_on_keyboard_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOUNDRY_CURSOR_API_KEY", "test-key")
    bundle = FOUNDRY_ROOT
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        bundle / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    fake_bridge = {
        "ok": True,
        "started": True,
        "bridge_url": "http://127.0.0.1:18791/v1/agent",
        "pid": 4242,
        "workspace": str(workspace),
        "health": {"ok": True},
    }
    args = argparse.Namespace(
        workspace=str(workspace),
        registry=str(bundle),
        json=True,
        foreground=True,
        skip_preflight=True,
    )

    def _sleep_raise(_seconds: float) -> None:
        raise KeyboardInterrupt

    with patch.object(up_commands, "reconcile_bridge", return_value=fake_bridge):
        with patch.object(up_commands, "host_is_running", return_value=False):
            with patch.object(up_commands, "cmd_host_start") as start:
                start.return_value = {"ok": True, "started": True, "pid": 5252}
                with patch.object(up_commands, "cmd_host_stop") as host_stop:
                    host_stop.return_value = {"ok": True, "stopped": True}
                    with patch.object(up_commands, "stop_bridge") as stop_bridge:
                        stop_bridge.return_value = {"ok": True, "stopped": True}
                        with patch(
                            "foundry_cli.up_commands.host_process_dimension",
                            return_value={"ok": True, "pid": 5252},
                        ):
                            with patch(
                                "foundry_cli.up_commands.host_health_dimension",
                                return_value={"ok": True},
                            ):
                                with patch(
                                    "foundry_cli.up_commands.adapter_dimension",
                                    return_value={
                                        "ok": True,
                                        "configured": True,
                                        "reachable": True,
                                    },
                                ):
                                    with patch(
                                        "foundry_cli.up_commands.bridge_readiness_from_url",
                                        return_value={"ok": True, "url": fake_bridge["bridge_url"]},
                                    ):
                                        with patch("time.sleep", side_effect=_sleep_raise):
                                            result = cmd_up(args)

    assert result.get("ok") is True
    assert result.get("foreground") is True
    assert result.get("ready") is False
    shutdown = result.get("foreground_shutdown")
    assert isinstance(shutdown, dict)
    assert shutdown.get("shutdown") is True
    assert shutdown.get("message")
    host_stop.assert_called()
    stop_bridge.assert_called_once_with(workspace.resolve())
