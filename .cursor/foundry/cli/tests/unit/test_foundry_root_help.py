"""Golden and regression tests for curriculum root help (cli-operator-ux P3)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from foundry_cli.help_catalog import LISTED_HELP_SECTIONS, UNLISTED_TOP_LEVEL_COMMANDS, listed_command_names
from foundry_cli.parser import build_parser
from tests.acceptance.helpers import CLI_ENTRY
from tests.conftest import REPO_ROOT

GOLDEN_PATH = Path(__file__).with_name("fixtures") / "foundry_root_help.txt"


def _run_foundry(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI_ENTRY), *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_root_help_matches_golden() -> None:
    completed = _run_foundry("-h")
    assert completed.returncode == 0, completed.stderr
    golden = GOLDEN_PATH.read_text(encoding="utf-8")
    assert completed.stdout == golden


def test_bare_foundry_shows_same_help_as_h() -> None:
    bare = _run_foundry()
    with_h = _run_foundry("-h")
    assert bare.returncode == 0
    assert bare.stdout == with_h.stdout


def test_root_help_excludes_unlisted_commands() -> None:
    completed = _run_foundry("-h")
    stdout = completed.stdout
    for name in ("host", "run", "tui", "bridge", "cli"):
        assert name in UNLISTED_TOP_LEVEL_COMMANDS
        assert re.search(rf"^  {re.escape(name)}\s", stdout, re.MULTILINE) is None


def test_root_help_includes_all_listed_commands_in_sections() -> None:
    completed = _run_foundry("-h")
    stdout = completed.stdout
    for title, commands in LISTED_HELP_SECTIONS:
        assert f"{title}:" in stdout
        for cmd in commands:
            assert f"  {cmd}" in stdout
    assert listed_command_names() == frozenset(
        cmd for _, cmds in LISTED_HELP_SECTIONS for cmd in cmds
    )


def test_shape_subcommand_help_unchanged_subprocess() -> None:
    completed = _run_foundry("shape", "-h")
    assert completed.returncode == 0, completed.stderr
    assert "usage: foundry shape" in completed.stdout
    assert "--input" in completed.stdout or "--input-file" in completed.stdout


def test_parser_still_registers_unlisted_for_dispatch() -> None:
    helps = build_parser()
    from foundry_cli.help_catalog import subcommand_help_map

    command_helps = subcommand_help_map(helps)
    for name in UNLISTED_TOP_LEVEL_COMMANDS:
        assert name in command_helps
