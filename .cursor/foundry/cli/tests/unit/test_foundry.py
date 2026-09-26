"""Unit tests for foundry.py CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from unittest.mock import patch

import foundry as foundry_module
from foundry import (
    FORMATTER_REGISTRY,
    _command_key,
    _format_error,
    _format_json,
    _format_result,
)
from tests.acceptance.helpers import CLI_ENTRY
from tests.conftest import FOUNDRY_ROOT, REPO_ROOT
from tests.unit.constants import ERROR_INVALID_FLAGS, FIXTURE_RUN_DIR


def _args(**kwargs: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "command": "run",
        "run_command": "context",
        "json": False,
        "markdown": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_run_context_rejects_json_and_markdown_together() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI_ENTRY),
            "--workspace",
            str(REPO_ROOT),
            "--registry",
            str(FOUNDRY_ROOT),
            "--json",
            "run",
            "context",
            "--run-dir",
            str(FIXTURE_RUN_DIR),
            "--markdown",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1, completed.stdout or completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == ERROR_INVALID_FLAGS


def test_formatter_registry_covers_success_commands() -> None:
    expected_keys = {
        ("run", "context"),
        ("catalog", "build"),
        ("doc", "build"),
        ("dev", "docs"),
        ("dev", "unit"),
        ("dev", "acceptance"),
        ("dev", "all"),
    }
    assert expected_keys.issubset(FORMATTER_REGISTRY.keys())


def test_format_json_prints_sorted_payload(capsys) -> None:
    result = {"ok": True, "run_id": "porcelain-0007", "status": "running"}
    _format_json(_args(json=True), result)
    captured = capsys.readouterr()
    assert json.loads(captured.out) == result


def test_format_error_prints_stderr(capsys) -> None:
    result = {"ok": False, "error": {"code": "RUN_EXISTS", "message": "already exists"}}
    _format_error(_args(), result)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error [RUN_EXISTS]: already exists\n"


def test_format_result_uses_registry_for_run_context(capsys) -> None:
    result = {
        "ok": True,
        "context": {
            "run_id": "porcelain-0007",
            "visit_id": "v-001",
            "node_id": "shape.intake",
            "lifecycle": "opened",
            "instructions": "registry:nodes/shape.intake/instructions.md",
        },
    }
    _format_result(_args(command="run", run_command="context"), result)
    captured = capsys.readouterr()
    assert "run=porcelain-0007 visit=v-001 node=shape.intake" in captured.out
    assert "lifecycle=opened" in captured.out


def test_format_result_json_takes_precedence_over_registry(capsys) -> None:
    result = {"ok": True, "context": {"run_id": "porcelain-0007"}}
    _format_result(_args(command="run", run_command="context", json=True), result)
    captured = capsys.readouterr()
    assert json.loads(captured.out) == result


def test_format_result_falls_back_to_error_for_unformatted_success(capsys) -> None:
    result = {"ok": True, "run_id": "porcelain-0007"}
    _format_result(_args(command="run", run_command="create"), result)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error [None]: None\n"


def test_format_result_markdown_read_failure_replaces_result() -> None:
    result = {
        "ok": True,
        "context": {
            "instructions_path": "/nonexistent/instructions.md",
            "run_id": "porcelain-0007",
        },
    }
    with patch("foundry.Path.read_text", side_effect=OSError("permission denied")):
        replaced = _format_result(
            _args(command="run", run_command="context", markdown=True),
            result,
        )
    assert replaced["ok"] is False
    assert replaced["error"]["code"] == "INSTRUCTIONS_READ_FAILED"


def test_command_key_visit_state_patch() -> None:
    args = argparse.Namespace(
        command="visit",
        visit_command="state",
        visit_state_command="patch",
    )
    assert _command_key(args) == ("visit", "state", "patch")


def test_command_key_dev_all() -> None:
    args = argparse.Namespace(command="dev", dev_command="all")
    assert _command_key(args) == ("dev", "all")


def test_main_returns_zero_on_success() -> None:
    with patch.object(foundry_module, "parse_args", return_value=_args()):
        with patch.object(foundry_module, "_dispatch", return_value={"ok": True, "run_id": "x"}):
            with patch.object(foundry_module, "_format_result", return_value={"ok": True, "run_id": "x"}):
                assert foundry_module.main([]) == 0


def test_main_returns_one_on_failure() -> None:
    failure = {"ok": False, "error": {"code": "X", "message": "y"}}
    with patch.object(foundry_module, "parse_args", return_value=_args()):
        with patch.object(foundry_module, "_dispatch", return_value=failure):
            with patch.object(foundry_module, "_format_result", return_value=failure):
                assert foundry_module.main([]) == 1
