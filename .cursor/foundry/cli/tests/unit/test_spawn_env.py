"""Detached child PYTHONPATH packaging."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.spawn_env import child_process_env, cli_package_root
from tests.conftest import FOUNDRY_ROOT


def test_child_process_env_includes_cli_root() -> None:
    bundle = FOUNDRY_ROOT
    env = child_process_env(bundle, base={})
    root = str(cli_package_root(bundle))
    assert root in env.get("PYTHONPATH", "")
