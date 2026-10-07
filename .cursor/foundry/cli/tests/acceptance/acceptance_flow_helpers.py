"""Workspace install and execute advance helpers for acceptance scenarios."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from tests.acceptance.constants import FIXTURE_APP
from tests.acceptance.helpers import FIXTURES_ROOT
from tests.unit.git_workspace import ensure_clean_git_workspace
from tests.unit.implementation_flow_helpers import (
    advance_snapshot_through_stub_execute,
    authorize_execute_start,
)


def install_run_fixture_at_workspace_root(tmp_path: Path, fixture_name: str) -> tuple[Path, str]:
    """Copy a committed run fixture under ``tmp_path/.foundry/runs``; return workspace and run_id."""
    src = FIXTURES_ROOT / fixture_name
    snapshot = json.loads((src / "snapshot.json").read_text(encoding="utf-8"))
    run_id = str(snapshot.get("run_id") or fixture_name)
    dest = tmp_path / ".foundry" / "runs" / run_id
    shutil.copytree(src, dest)
    return tmp_path, run_id


def copy_foundry_test_app_manifest(workspace: Path) -> None:
    foundry_dir = workspace / ".foundry"
    foundry_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURE_APP, foundry_dir / "app.yaml")


def ensure_execute_workspace_manifest_and_clean_git(workspace: Path) -> None:
    copy_foundry_test_app_manifest(workspace)
    ensure_clean_git_workspace(workspace)


def merge_foundry_test_app_tree(workspace: Path) -> None:
    from tests.conftest import FOUNDRY_ROOT

    shutil.copytree(
        FOUNDRY_ROOT / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
        dirs_exist_ok=True,
    )


def advance_acceptance_run_to_execute_plan(acceptance: dict[str, Any]) -> None:
    """Authorize execute.start and advance stub execute until execute.plan is ready."""
    workspace = Path(acceptance["workspace"])
    run_id = str(acceptance["run_id"])
    merge_foundry_test_app_tree(workspace)
    authorize_execute_start(workspace, run_id)
    snapshot = advance_snapshot_through_stub_execute(
        workspace,
        run_id,
        stop_at="execute.plan",
        submit_plan_judgment_if_waiting=False,
    )
    active = snapshot.get("active_visit") or {}
    node_id = str(active.get("node_id") or "")
    if node_id != "execute.plan":
        raise AssertionError(f"did not reach execute.plan (active {node_id!r})")
    wait = snapshot.get("wait")
    if node_id == "execute.plan" and wait is None:
        return
    if isinstance(wait, dict) and wait.get("kind") == "agent":
        return
    if node_id == "execute.build":
        raise AssertionError("advanced past execute.plan without stopping")

