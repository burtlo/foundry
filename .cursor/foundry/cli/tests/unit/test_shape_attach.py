"""Unit tests for ``foundry shape --attach`` (P13 interactive attach)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_cli.tui_commands import _TUI_DEPRECATION, cmd_tui
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import shape_test_workspace

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"


def test_shape_attach_wires_interactive_launcher_after_intake(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Intake handoff prints first; then interactive attach launches for the new run."""
    import foundry as foundry_cli_main

    workspace = shape_test_workspace(tmp_path)
    launch_calls: list[str] = []

    def fake_attach(attach_args):
        launch_calls.append(str(getattr(attach_args, "run", "")))
        return {"ok": True, "launched": True, "run_id": launch_calls[-1]}

    with patch("foundry.cmd_attach", side_effect=fake_attach):
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
    assert len(launch_calls) == 1
    assert launch_calls[0].startswith("foundry-")
    out = capsys.readouterr().out
    assert "Shape request received." in out
    assert "Intake successful." in out
    assert "foundry attach" in out


def test_shape_attach_json_skips_interactive_launch(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    with patch("foundry.cmd_attach") as attach:
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
    attach.assert_not_called()
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body.get("ok") is True
    assert body.get("intake_complete") is True
    assert "event_type" not in result.stdout


def test_shape_attach_delegates_run_id_to_cmd_attach(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    args = argparse.Namespace(
        command="shape",
        workspace=str(workspace),
        registry=str(BUNDLE),
        json=False,
        local=True,
        no_host=True,
        input="Direct attach wiring",
        attach=True,
    )

    with patch("foundry.cmd_attach") as attach:
        attach.return_value = {"ok": True, "launched": True, "run_id": "foundry-test"}
        import foundry as foundry_cli_main

        foundry_cli_main._format_result(
            args,
            {
                "ok": True,
                "run_id": "foundry-test",
                "intake_complete": True,
                "intake_status": "passed",
            },
        )

    attach.assert_called_once()
    assert getattr(attach.call_args[0][0], "run") == "foundry-test"


def test_tui_prints_deprecation_and_delegates_to_attach(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = shape_test_workspace(tmp_path)
    args = type(
        "Args",
        (),
        {
            "workspace": str(workspace),
            "registry": str(BUNDLE),
            "json": False,
            "run": None,
        },
    )()

    with patch("foundry_cli.tui_commands.cmd_attach") as attach:
        attach.return_value = {"ok": True, "launched": True}
        result = cmd_tui(args)

    assert result.get("ok") is True
    attach.assert_called_once_with(args)
    err = capsys.readouterr().err
    assert _TUI_DEPRECATION in err


def test_tui_passes_run_flag_to_attach(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    args = type(
        "Args",
        (),
        {
            "workspace": str(workspace),
            "registry": str(BUNDLE),
            "json": False,
            "run": "foundry-0001",
        },
    )()

    with patch("foundry_cli.user_cli.sys.stdout.isatty", return_value=True):
        with patch("foundry_cli.tui.run_interactive_attach") as launch:
            result = cmd_tui(args)

    assert result.get("ok") is True
    launch.assert_called_once()
    assert launch.call_args.kwargs["run_id"] == "foundry-0001"
