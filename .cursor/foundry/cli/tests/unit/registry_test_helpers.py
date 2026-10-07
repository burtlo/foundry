"""Minimal registry bundle copies for catalog and ref validation tests."""

from __future__ import annotations

import shutil
from pathlib import Path

from tests.conftest import FOUNDRY_ROOT


def bundle_with_step_stubs(tmp_path: Path) -> Path:
    """Copy Foundry bundle (and agents tree when present) into a temp cursor layout."""
    cursor_root = tmp_path / "cursor"
    dest = cursor_root / "foundry"
    shutil.copytree(FOUNDRY_ROOT, dest)
    agents_src = FOUNDRY_ROOT.parent / "agents"
    if agents_src.is_dir():
        shutil.copytree(agents_src, cursor_root / "agents")
    return dest
