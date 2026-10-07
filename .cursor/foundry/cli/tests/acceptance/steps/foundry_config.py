"""Step definitions for foundry_config.feature."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pytest_bdd import given, then

from tests.acceptance.acceptance_config_helpers import prepare_bundle_target
from tests.conftest import FOUNDRY_ROOT


@given("a temporary config workspace without foundry.yaml")
def config_workspace_bare(acceptance, tmp_path) -> None:
    workspace = tmp_path / "config-app"
    workspace.mkdir(parents=True)
    bundle_target = tmp_path / "bundle"
    prepare_bundle_target(bundle_target)
    registry_ref = Path(os.path.relpath(bundle_target, workspace)).as_posix()
    acceptance["workspace"] = workspace
    acceptance["registry"] = FOUNDRY_ROOT
    acceptance["bundle_target"] = bundle_target
    acceptance["config_init_registry"] = registry_ref
    acceptance["fixture_name"] = None
    acceptance["run_id"] = None
    acceptance["omit_registry"] = False


@given("a temporary config workspace with foundry.yaml pointing at bundle")
def config_workspace_with_yaml(acceptance, tmp_path) -> None:
    workspace = tmp_path / "config-app"
    workspace.mkdir(parents=True)
    bundle_target = tmp_path / "bundle"
    prepare_bundle_target(bundle_target)
    registry_ref = Path(os.path.relpath(bundle_target, workspace)).as_posix()
    config_dir = workspace / ".foundry"
    config_dir.mkdir(parents=True)
    (config_dir / "foundry.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "registry": registry_ref}, sort_keys=False),
        encoding="utf-8",
    )
    acceptance["workspace"] = workspace
    acceptance["registry"] = FOUNDRY_ROOT
    acceptance["bundle_target"] = bundle_target
    acceptance["fixture_name"] = None
    acceptance["run_id"] = None
    acceptance["omit_registry"] = False


@given("a temporary config workspace with foundry.yaml pointing at in-workspace bundle")
def config_workspace_with_in_workspace_bundle(acceptance, tmp_path) -> None:
    workspace = tmp_path / "config-app"
    workspace.mkdir(parents=True)
    bundle_target = workspace / "bundle"
    prepare_bundle_target(bundle_target)
    registry_ref = Path(os.path.relpath(bundle_target, workspace)).as_posix()
    config_dir = workspace / ".foundry"
    config_dir.mkdir(parents=True)
    (config_dir / "foundry.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "registry": registry_ref}, sort_keys=False),
        encoding="utf-8",
    )
    acceptance["workspace"] = workspace
    acceptance["registry"] = FOUNDRY_ROOT
    acceptance["bundle_target"] = bundle_target
    acceptance["fixture_name"] = None
    acceptance["run_id"] = None
    acceptance["omit_registry"] = False


@given("a temporary config workspace with invalid foundry.yaml registry")
def config_workspace_invalid_registry(acceptance, tmp_path) -> None:
    workspace = tmp_path / "config-app"
    workspace.mkdir(parents=True)
    config_dir = workspace / ".foundry"
    config_dir.mkdir(parents=True)
    (config_dir / "foundry.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "registry": "../missing-bundle"}, sort_keys=False),
        encoding="utf-8",
    )
    acceptance["workspace"] = workspace
    acceptance["registry"] = FOUNDRY_ROOT
    acceptance["fixture_name"] = None
    acceptance["run_id"] = None
    acceptance["omit_registry"] = False


@given("cli resolve omits global registry flag")
def cli_resolve_omit_registry(acceptance) -> None:
    acceptance["omit_registry"] = True


@then("workspace foundry config file does not exist")
def assert_foundry_config_missing(acceptance) -> None:
    path = Path(acceptance["workspace"]) / ".foundry" / "foundry.yaml"
    assert not path.is_file(), f"expected no foundry config at {path}"


@then("workspace foundry config file exists")
def assert_foundry_config_exists(acceptance) -> None:
    path = Path(acceptance["workspace"]) / ".foundry" / "foundry.yaml"
    assert path.is_file(), f"expected foundry config at {path}"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    assert data.get("registry")
