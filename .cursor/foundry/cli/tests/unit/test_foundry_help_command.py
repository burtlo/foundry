"""Golden and regression tests for ``foundry help`` (cli-operator-ux P4)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

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


def test_help_matches_curated_root_help() -> None:
    help_out = _run_foundry("help")
    root_out = _run_foundry("-h")
    assert help_out.returncode == 0, help_out.stderr
    assert root_out.returncode == 0, root_out.stderr
    assert help_out.stdout == root_out.stdout
    assert help_out.stdout == GOLDEN_PATH.read_text(encoding="utf-8")


def test_help_all_lists_unlisted_commands() -> None:
    completed = _run_foundry("help", "-a")
    assert completed.returncode == 0, completed.stderr
    stdout = completed.stdout
    for name in ("host", "run", "dev"):
        assert re.search(rf"^  {re.escape(name)}\s", stdout, re.MULTILINE) is not None


def test_help_all_includes_listed_commands() -> None:
    completed = _run_foundry("help", "-a")
    stdout = completed.stdout
    for name in ("config", "shape", "up", "down"):
        assert re.search(rf"^  {re.escape(name)}\s", stdout, re.MULTILINE) is not None


def test_help_shape_documents_shape_flags() -> None:
    via_help = _run_foundry("help", "shape")
    direct = _run_foundry("shape", "-h")
    assert via_help.returncode == 0, via_help.stderr
    assert direct.returncode == 0, direct.stderr
    assert via_help.stdout == direct.stdout
    assert "--input" in via_help.stdout or "--input-file" in via_help.stdout


def test_help_unknown_command_nonzero() -> None:
    completed = _run_foundry("help", "not-a-command")
    assert completed.returncode == 1
    assert "not-a-command" in completed.stderr or "not-a-command" in completed.stdout
