"""Step definitions for execute_slice_2a.feature."""

from __future__ import annotations

import shutil
from pathlib import Path

from pytest_bdd import given, then

from tests.acceptance.constants import FIXTURE_APP
from tests.unit.git_workspace import ensure_clean_git_workspace


def _prepare_execute_workspace(acceptance) -> None:
    workspace = Path(acceptance["workspace"])
    foundry_dir = workspace / ".foundry"
    foundry_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURE_APP, foundry_dir / "app.yaml")
    ensure_clean_git_workspace(workspace)


@given("execute workspace has app manifest and clean git")
def execute_workspace_ready_given(acceptance) -> None:
    _prepare_execute_workspace(acceptance)


@then("execute workspace has app manifest and clean git")
def execute_workspace_ready_then(acceptance) -> None:
    _prepare_execute_workspace(acceptance)
