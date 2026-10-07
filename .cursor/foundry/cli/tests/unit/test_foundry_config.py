"""Unit tests for foundry_cli.foundry_config."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from foundry_cli.foundry_config import (
    foundry_config_path,
    init_foundry_config,
    load_foundry_config,
    resolve_registry_bundle,
    resolve_registry_path_from_config,
    validate_foundry_config,
)
from tests.conftest import FOUNDRY_ROOT
from tests.flow_registry_stubs import write_stub_flow_registry


def _write_foundry_config(workspace: Path, registry_ref: str, *, flow: str | None = None) -> None:
    data: dict = {"schema_version": 1, "registry": registry_ref}
    if flow is not None:
        data["flow"] = flow
    target = workspace / ".foundry" / "foundry.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_resolve_from_foundry_yaml_relative_path(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FOUNDRY_REGISTRY", raising=False)
    workspace = tmp_path / "app"
    workspace.mkdir()
    bundle = tmp_path / "registry"
    write_stub_flow_registry(bundle)
    _write_foundry_config(workspace, "../registry")

    resolved, source = resolve_registry_bundle(workspace)
    assert resolved == bundle.resolve()
    assert source == "foundry.yaml"


def test_cli_flag_overrides_foundry_yaml(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FOUNDRY_REGISTRY", raising=False)
    workspace = tmp_path / "app"
    workspace.mkdir()
    config_bundle = tmp_path / "from-config"
    cli_bundle = tmp_path / "from-cli"
    for bundle in (config_bundle, cli_bundle):
        write_stub_flow_registry(bundle)
    _write_foundry_config(workspace, "../from-config")

    resolved, source = resolve_registry_bundle(workspace, explicit_registry=cli_bundle)
    assert resolved == cli_bundle.resolve()
    assert source == "cli_flag"


def test_env_overrides_foundry_yaml(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    config_bundle = tmp_path / "from-config"
    env_bundle = tmp_path / "from-env"
    for bundle in (config_bundle, env_bundle):
        write_stub_flow_registry(bundle)
    _write_foundry_config(workspace, "../from-config")
    monkeypatch.setenv("FOUNDRY_REGISTRY", str(env_bundle))

    resolved, source = resolve_registry_bundle(workspace)
    assert resolved == env_bundle.resolve()
    assert source == "env"


def test_workspace_bundle_fallback_without_foundry_yaml(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FOUNDRY_REGISTRY", raising=False)
    workspace = tmp_path / "repo"
    bundle = workspace / ".cursor" / "foundry"
    write_stub_flow_registry(bundle)

    resolved, source = resolve_registry_bundle(workspace)
    assert resolved == bundle.resolve()
    assert source == "workspace_bundle"


def test_missing_foundry_yaml_raises_helpful_error(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FOUNDRY_REGISTRY", raising=False)
    workspace = tmp_path / "bare"
    workspace.mkdir()

    with pytest.raises(FileNotFoundError, match="foundry config init"):
        resolve_registry_bundle(workspace)


def test_invalid_foundry_yaml_registry_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FOUNDRY_REGISTRY", raising=False)
    workspace = tmp_path / "app"
    workspace.mkdir()
    _write_foundry_config(workspace, "../missing-bundle")

    with pytest.raises(FileNotFoundError, match="Registry bundle"):
        resolve_registry_bundle(workspace)


def test_validate_rejects_bad_schema(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FOUNDRY_REGISTRY", raising=False)
    workspace = tmp_path / "app"
    workspace.mkdir()
    bundle = tmp_path / "registry"
    write_stub_flow_registry(bundle)
    schema_dir = bundle / "schemas"
    schema_dir.mkdir(parents=True)
    schema_src = FOUNDRY_ROOT / "schemas" / "foundry-config.schema.json"
    (schema_dir / "foundry-config.schema.json").write_text(
        schema_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    target = workspace / ".foundry" / "foundry.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(
        yaml.safe_dump({"schema_version": 1, "registry": "../registry", "extra": True}),
        encoding="utf-8",
    )

    result = validate_foundry_config(workspace)
    assert result["ok"] is False
    assert any("additional properties" in err.lower() for err in result["errors"])


def test_load_foundry_config_round_trip(tmp_path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    _write_foundry_config(workspace, "../foundry/.cursor/foundry", flow="implementation")

    path, data = load_foundry_config(workspace)
    assert path == foundry_config_path(workspace)
    assert data["registry"] == "../foundry/.cursor/foundry"


def test_resolve_registry_path_from_config_rejects_absolute(tmp_path) -> None:
    with pytest.raises(ValueError, match="relative"):
        resolve_registry_path_from_config("/absolute/path", tmp_path)


def test_init_foundry_config_writes_file(tmp_path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    bundle = tmp_path / "registry"
    write_stub_flow_registry(bundle)

    result = init_foundry_config(workspace, FOUNDRY_ROOT, registry_ref="../registry")
    assert result["written"] is True
    assert foundry_config_path(workspace).is_file()
