"""Acceptance steps for run archive."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
import yaml
from pytest_bdd import given, parsers, then, when

from tests.acceptance.acceptance_config_helpers import prepare_bundle_target
from tests.acceptance.acceptance_invoke import invoke_acceptance_command
from tests.conftest import FOUNDRY_ROOT

pytestmark = pytest.mark.usefixtures("acceptance")


@given(parsers.parse('a temporary archive workspace with a completed run "{run_id}"'))
def temporary_archive_workspace(acceptance: dict, tmp_path: Path, run_id: str) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    bundle_target = tmp_path / "bundle"
    prepare_bundle_target(bundle_target)
    registry_ref = Path(os.path.relpath(bundle_target, workspace)).as_posix()
    foundry_dir = workspace / ".foundry"
    foundry_dir.mkdir()
    (foundry_dir / "foundry.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "registry": registry_ref}, sort_keys=False),
        encoding="utf-8",
    )
    (foundry_dir / "app.yaml").write_text(
        """schema_version: 1
id: porcelain
commands:
  build:
    default:
      argv: ["make", "build"]
      cwd: "."
      timeout_seconds: 600
  test:
    default:
      argv: ["make", "test"]
      cwd: "."
      timeout_seconds: 600
verification:
  implementation:
    - build
    - test
  post_repair:
    - build
    - test
builders:
  default_owner: general-builder
  routes:
    - id: default
      owner: general-builder
      priority: 0
      globs:
        - "**/*"
""",
        encoding="utf-8",
    )

    run_dir = foundry_dir / "runs" / run_id
    fixture = FOUNDRY_ROOT / "fixtures" / "runs" / "porcelain-0007-v005-present-gate"
    shutil.copytree(fixture, run_dir)
    snapshot_path = run_dir / "snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["run_id"] = run_id
    snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    acceptance["workspace"] = str(workspace)
    acceptance["registry"] = str(FOUNDRY_ROOT)
    acceptance["omit_registry"] = False
    acceptance["run_id"] = run_id
    acceptance["archive_root"] = str(tmp_path / "archive-store")


@given(parsers.parse('the foundry runs store contains archive "{slug}"'))
def existing_archive_store(acceptance: dict, slug: str) -> None:
    archive_root = Path(acceptance["archive_root"])
    (archive_root / slug).mkdir(parents=True)


@when(parsers.parse('I invoke "run archive" with json output'))
@when(parsers.parse('I invoke "run archive" with json output and flag "{flag}"'))
def invoke_run_archive(acceptance: dict, flag: str | None = None) -> None:
    invoke_acceptance_command(
        acceptance,
        "run archive",
        extra_flags=[flag] if flag else [],
        extra_argv=["--archive-root", acceptance["archive_root"]],
    )


@then(parsers.parse('workspace run directory "{run_id}" still exists'))
def workspace_run_still_exists(acceptance: dict, run_id: str) -> None:
    path = Path(acceptance["workspace"]) / ".foundry" / "runs" / run_id
    assert path.is_dir(), f"expected run dir to exist: {path}"


@then(parsers.parse('workspace run directory "{run_id}" does not exist'))
def workspace_run_removed(acceptance: dict, run_id: str) -> None:
    path = Path(acceptance["workspace"]) / ".foundry" / "runs" / run_id
    assert not path.exists(), f"expected run dir to be removed: {path}"


@then(parsers.parse('archived run "{slug}" contains "{relative_path}"'))
def archived_run_contains(acceptance: dict, slug: str, relative_path: str) -> None:
    payload = acceptance.get("payload") or {}
    archive_path = payload.get("archive_path")
    if archive_path:
        path = Path(archive_path) / relative_path
    else:
        path = Path(acceptance["archive_root"]) / slug / relative_path
    assert path.is_file(), f"expected archived file: {path}"
