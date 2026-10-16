"""Unit tests for ``foundry ledger follow`` and attach stream migration (P10)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_cli.command_context import CommandContext
from foundry_cli.run_service import create_run
from foundry_cli.user_cli import cmd_attach, cmd_ledger_follow, stream_ledger_follow
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import shape_test_workspace

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"


def _args_namespace(workspace: Path, **overrides: object) -> argparse.Namespace:
    base = {
        "workspace": str(workspace),
        "registry": str(BUNDLE),
        "json": False,
        "local": True,
        "no_follow": False,
        "after_seq": 0,
        "run": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_ledger_follow_streams_json_lines(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = shape_test_workspace(tmp_path)
    created = create_run(workspace=workspace, bundle=BUNDLE, work_prompt="Ledger follow")
    run_id = str(created["run_id"])

    ctx = CommandContext(workspace=workspace, bundle=BUNDLE)
    args = _args_namespace(workspace, run=run_id)

    with patch("foundry_cli.user_cli.time.sleep", side_effect=KeyboardInterrupt):
        result = cmd_ledger_follow(args)

    assert result.get("ok") is True
    assert result.get("detached") is True
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "expected at least one JSON event line on stdout"
    for line in out:
        payload = json.loads(line)
        assert isinstance(payload, dict)


def test_stream_ledger_follow_same_as_cmd(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = shape_test_workspace(tmp_path)
    created = create_run(workspace=workspace, bundle=BUNDLE, work_prompt="Stream helper")
    run_id = str(created["run_id"])
    ctx = CommandContext(workspace=workspace, bundle=BUNDLE)
    args = _args_namespace(workspace)

    with patch("foundry_cli.user_cli.time.sleep", side_effect=KeyboardInterrupt):
        result = stream_ledger_follow(ctx, args, run_id=run_id)

    assert result.get("ok") is True
    assert capsys.readouterr().out.strip()


def test_attach_default_launches_interactive(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    created = create_run(workspace=workspace, bundle=BUNDLE, work_prompt="Attach interactive")
    run_id = str(created["run_id"])
    args = _args_namespace(workspace, run=run_id)

    with patch("foundry_cli.user_cli.sys.stdout.isatty", return_value=True):
        with patch("foundry_cli.tui.run_interactive_attach") as launch:
            result = cmd_attach(args)

    assert result.get("ok") is True
    assert result.get("launched") is True
    launch.assert_called_once()
    _, kwargs = launch.call_args
    assert kwargs["workspace"] == workspace
    assert kwargs["registry"] == str(BUNDLE)
    assert kwargs["run_id"] == run_id


def test_attach_no_run_launches_list(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    args = _args_namespace(workspace, run=None)

    with patch("foundry_cli.user_cli.sys.stdout.isatty", return_value=True):
        with patch("foundry_cli.tui.run_interactive_attach") as launch:
            result = cmd_attach(args)

    assert result.get("ok") is True
    launch.assert_called_once()
    assert launch.call_args.kwargs["run_id"] is None


def test_attach_non_tty_points_to_ledger(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    created = create_run(workspace=workspace, bundle=BUNDLE, work_prompt="Attach non-tty")
    run_id = str(created["run_id"])
    args = _args_namespace(workspace, run=run_id)

    with patch("foundry_cli.user_cli.sys.stdout.isatty", return_value=False):
        result = cmd_attach(args)

    assert result.get("ok") is False
    message = str(result.get("error", {}).get("message", ""))
    assert result.get("error", {}).get("code") == "ATTACH_NOT_TTY"
    assert "ledger follow" in message
    assert "ledger show" in message


def test_attach_json_batch_still_works(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    created = create_run(workspace=workspace, bundle=BUNDLE, work_prompt="Attach batch")
    run_id = str(created["run_id"])
    args = _args_namespace(workspace, run=run_id, json=True, no_follow=True)

    result = cmd_attach(args)

    assert result.get("ok") is True
    assert result.get("run_id") == run_id
    assert isinstance(result.get("events"), list)


def test_ledger_follow_parser_dispatch(tmp_path: Path) -> None:
    import foundry as foundry_cli_main

    workspace = shape_test_workspace(tmp_path)
    created = create_run(workspace=workspace, bundle=BUNDLE, work_prompt="Dispatch follow")
    run_id = str(created["run_id"])

    with patch("foundry_cli.user_cli.stream_ledger_follow") as stream:
        stream.return_value = {"ok": True, "detached": True, "run_id": run_id, "after_seq": 0}
        exit_code = foundry_cli_main.main(
            [
                "--workspace",
                str(workspace),
                "--registry",
                str(BUNDLE),
                "ledger",
                "follow",
                "--run",
                run_id,
                "--local",
            ]
        )

    assert exit_code == 0
    stream.assert_called_once()


def test_attach_piped_stdout_migration_exit(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    created = create_run(workspace=workspace, bundle=BUNDLE, work_prompt="Piped attach")
    run_id = str(created["run_id"])

    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            "attach",
            run_id,
            "--local",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode != 0
    err = result.stderr + result.stdout
    assert "ledger follow" in err.lower() or "ledger follow" in err
    assert "ledger show" in err.lower() or "ledger show" in err
