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


def bundle_without_steps_dir(tmp_path: Path, *, name: str = "bundle-no-steps") -> Path:
    """Minimal temp bundle copy with the registry ``steps/`` tree removed."""
    bundle = tmp_path / name
    shutil.copytree(FOUNDRY_ROOT, bundle)
    steps = bundle / "steps"
    if steps.is_dir():
        shutil.rmtree(steps)
    return bundle
