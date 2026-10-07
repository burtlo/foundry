"""Thin wrappers for steward context packet unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.context import assemble_context
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT


def assemble_step_context(
    run_dir: Path,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    *,
    foundry_bundle: Path = FOUNDRY_ROOT,
) -> dict[str, Any]:
    _, flow = load_registry(foundry_bundle)
    return assemble_context(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
