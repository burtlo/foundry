"""Step definitions for foundry_config.feature."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml
from pytest_bdd import given, then

from tests.conftest import FOUNDRY_ROOT


def _prepare_bundle_target(bundle_target: Path) -> None:
    bundle_target.mkdir(parents=True, exist_ok=True)
    (bundle_target / "flows").mkdir(parents=True, exist_ok=True)
    factory_flow = FOUNDRY_ROOT / "flows" / "factory-flow.yaml"
    if factory_flow.is_file():
        shutil.copy2(factory_flow, bundle_target / "flows" / "factory-flow.yaml")
    else:
        (bundle_target / "flows" / "factory-flow.yaml").write_text("flow: test\n", encoding="utf-8")
    schemas_dest = bundle_target / "schemas"
    if schemas_dest.exists():
        shutil.rmtree(schemas_dest)
    shutil.copytree(FOUNDRY_ROOT / "schemas", schemas_dest)
    cli_dir = bundle_target / "cli"
    cli_dir.mkdir(parents=True, exist_ok=True)
    foundry_sh = FOUNDRY_ROOT / "cli" / "foundry.sh"
    if foundry_sh.is_file():
        shutil.copy2(foundry_sh, cli_dir / "foundry.sh")
    else:
        (cli_dir / "foundry.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")


@given("a temporary config workspace without foundry.yaml")
def config_workspace_bare(acceptance, tmp_path) -> None:
    workspace = tmp_path / "config-app"
    workspace.mkdir(parents=True)
    bundle_target = tmp_path / "bundle"
    _prepare_bundle_target(bundle_target)
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
    _prepare_bundle_target(bundle_target)
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
    _prepare_bundle_target(bundle_target)
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
