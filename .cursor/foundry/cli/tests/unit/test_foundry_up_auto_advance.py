"""``foundry up`` enables host auto-advance on start."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_cli.host_commands import configure_host_start_for_up
from foundry_cli.up_commands import cmd_up
from tests.conftest import FOUNDRY_ROOT


def test_configure_host_start_for_up_sets_defaults() -> None:
    args = argparse.Namespace()
    configure_host_start_for_up(args)
    assert args.auto_advance is True
    assert args.auto_advance_interval == 2.0


def test_configure_host_start_for_up_preserves_interval() -> None:
    args = argparse.Namespace(auto_advance_interval=5.0)
    configure_host_start_for_up(args)
    assert args.auto_advance is True
    assert args.auto_advance_interval == 5.0


def test_cmd_up_passes_auto_advance_to_host_start(
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
        foreground=False,
    )
    captured: dict[str, object] = {}

    def _capture_start(ns: argparse.Namespace) -> dict[str, object]:
        captured["auto_advance"] = getattr(ns, "auto_advance", None)
        captured["auto_advance_interval"] = getattr(ns, "auto_advance_interval", None)
        return {"ok": True, "started": True, "pid": 5252, "auto_advance": True}

    with patch("foundry_cli.up_commands.reconcile_bridge", return_value=fake_bridge):
        with patch("foundry_cli.up_commands.host_is_running", return_value=False):
            with patch("foundry_cli.up_commands.cmd_host_start", side_effect=_capture_start):
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
                            return_value={"ok": True, "configured": True, "reachable": True},
                        ):
                            with patch(
                                "foundry_cli.up_commands.bridge_readiness_from_url",
                                return_value={"ok": True, "url": fake_bridge["bridge_url"]},
                            ):
                                result = cmd_up(args)

    assert result.get("ok") is True
    assert captured.get("auto_advance") is True
    assert captured.get("auto_advance_interval") == 2.0
