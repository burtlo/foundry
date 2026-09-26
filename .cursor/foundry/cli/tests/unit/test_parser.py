"""Unit tests for global CLI flag pre-parsing."""

from __future__ import annotations

import json
import subprocess
import sys

from foundry_cli.parser import extract_global_flags, parse_args
from tests.acceptance.helpers import CLI_ENTRY
from tests.conftest import FOUNDRY_ROOT, REPO_ROOT


def test_extract_global_flags_json_at_end() -> None:
    globals_out, cleaned = extract_global_flags(["cli", "resolve", "--json"])
    assert globals_out["json"] is True
    assert cleaned == ["cli", "resolve"]


def test_extract_global_flags_json_at_start() -> None:
    globals_out, cleaned = extract_global_flags(["--json", "cli", "resolve"])
    assert globals_out["json"] is True
    assert cleaned == ["cli", "resolve"]


def test_extract_global_flags_workspace_and_registry_scattered() -> None:
    globals_out, cleaned = extract_global_flags(
        [
            "run",
            "create",
            "--workspace",
            "/ws",
            "--flow",
            "implementation",
            "--registry",
            "/reg",
            "--json",
        ]
    )
    assert globals_out == {"workspace": "/ws", "registry": "/reg", "json": True}
    assert cleaned == ["run", "create", "--flow", "implementation"]


def test_extract_global_flags_preserves_config_init_registry() -> None:
    globals_out, cleaned = extract_global_flags(
        ["config", "init", "--registry", "relative/path", "--json"]
    )
    assert globals_out["json"] is True
    assert globals_out["registry"] is None
    assert cleaned == ["config", "init", "--registry", "relative/path"]


def test_parse_args_cli_resolve_json_at_end() -> None:
    args = parse_args(["cli", "resolve", "--json"])
    assert args.command == "cli"
    assert args.cli_command == "resolve"
    assert args.json is True


def test_parse_args_cli_resolve_json_at_start() -> None:
    args = parse_args(["--json", "cli", "resolve"])
    assert args.command == "cli"
    assert args.cli_command == "resolve"
    assert args.json is True


def test_cli_resolve_json_at_end_subprocess() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI_ENTRY),
            "--workspace",
            str(REPO_ROOT),
            "--registry",
            str(FOUNDRY_ROOT),
            "cli",
            "resolve",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["registry_root"] == str(FOUNDRY_ROOT)


def test_cli_resolve_json_at_start_subprocess() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI_ENTRY),
            "--json",
            "--workspace",
            str(REPO_ROOT),
            "--registry",
            str(FOUNDRY_ROOT),
            "cli",
            "resolve",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["registry_root"] == str(FOUNDRY_ROOT)


def test_run_create_json_at_end_subprocess() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI_ENTRY),
            "--workspace",
            str(REPO_ROOT),
            "--registry",
            str(FOUNDRY_ROOT),
            "run",
            "create",
            "--flow",
            "implementation",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload.get("run_id")
