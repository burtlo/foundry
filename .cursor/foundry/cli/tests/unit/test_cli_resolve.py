"""Unit tests for cli resolve command."""

from __future__ import annotations

import argparse
from pathlib import Path

from foundry_cli.commands import cmd_cli_resolve
from foundry_cli.paths import cli_script_path
from tests.conftest import REPO_ROOT


def test_cmd_cli_resolve_includes_cli_path(bundle) -> None:
    args = argparse.Namespace(workspace=REPO_ROOT, registry=str(bundle))
    result = cmd_cli_resolve(args)
    assert result["ok"] is True
    assert result["cli_path"] == ".cursor/foundry/cli/foundry.sh"
    assert (REPO_ROOT / result["cli_path"]).resolve() == cli_script_path(bundle)
