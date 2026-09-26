"""Unit tests for app bootstrap (discover, init, validate)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from foundry_cli.app_bootstrap import discover_app, init_app_manifest, render_manifest, validate_manifest_data
from foundry_cli.app_manifest import validate_manifest
from tests.conftest import FOUNDRY_ROOT

FIXTURE_APP = FOUNDRY_ROOT / "fixtures" / "apps" / "foundry-test" / ".foundry" / "app.yaml"


def base_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": "sample-app",
        "commands": {
            "build": {
                "default": {
                    "argv": ["python", "-m", "build"],
                    "cwd": ".",
                    "timeout_seconds": 900,
                }
            },
            "test": {
                "default": {
                    "argv": ["python", "-m", "unittest"],
                    "cwd": ".",
                    "timeout_seconds": 1200,
                }
            },
        },
        "verification": {
            "implementation": ["build", "test"],
            "post_repair": ["build", "test"],
        },
        "builders": {
            "default_owner": "general-builder",
            "routes": [
                {
                    "id": "default",
                    "owner": "general-builder",
                    "priority": 0,
                    "globs": ["**/*"],
                }
            ],
        },
    }


def write_manifest_input(tmp_path: Path, manifest: dict, name: str = "input.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return path


def test_discover_makefile_and_go_mod(tmp_path) -> None:
    workspace = tmp_path / "my-app"
    workspace.mkdir()
    (workspace / "Makefile").write_text("build:\n\techo build\n\ntest:\n\techo test\n", encoding="utf-8")
    (workspace / "go.mod").write_text("module example.com/app\n\ngo 1.22\n", encoding="utf-8")

    result = discover_app(workspace)

    manifest = result["proposed_manifest"]
    assert manifest["schema_version"] == 1
    assert manifest["id"] == "my-app"
    assert manifest["commands"]["build"]["default"]["argv"] == ["make", "build"]
    assert manifest["commands"]["test"]["default"]["argv"] == ["make", "test"]
    assert manifest["builders"]["default_owner"] == "general-builder"
    assert manifest["builders"]["routes"][0]["owner"] == "general-builder"
    assert "documentation" not in manifest


def test_discover_pyproject(tmp_path) -> None:
    workspace = tmp_path / "py-service"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text("[project]\nname = 'py-service'\n", encoding="utf-8")

    result = discover_app(workspace)
    manifest = result["proposed_manifest"]
    assert manifest["commands"]["test"]["default"]["argv"] == ["python", "-m", "pytest"]
    assert "python" in manifest.get("tags", [])


def test_validate_manifest_data_rejects_documentation(bundle) -> None:
    manifest = base_manifest()
    manifest["documentation"] = {"model": "feature-records", "config": {}}
    errors = validate_manifest_data(manifest, bundle)
    assert any("documentation" in error for error in errors)


def test_init_dry_run_writes_nothing(tmp_path, bundle) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    source = write_manifest_input(tmp_path, base_manifest())

    result = init_app_manifest(workspace, source, bundle, dry_run=True)

    assert result["dry_run"] is True
    assert result["changed"] is True
    assert result["written"] is False
    assert "schema_version: 1" in result["rendered_manifest"]
    assert not (workspace / ".foundry" / "app.yaml").exists()


def test_init_writes_and_is_idempotent(tmp_path, bundle) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    source = write_manifest_input(tmp_path, base_manifest())

    first = init_app_manifest(workspace, source, bundle)
    second = init_app_manifest(workspace, source, bundle)

    assert first["written"] is True
    assert second["changed"] is False
    assert second["written"] is False
    validation = validate_manifest(workspace, bundle)
    assert validation["ok"] is True
    assert validation["manifest_id"] == "sample-app"


def test_init_refuses_overwrite_without_force(tmp_path, bundle) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    first = base_manifest()
    second = base_manifest()
    second["id"] = "replacement-app"
    init_app_manifest(workspace, write_manifest_input(tmp_path, first, "first.yaml"), bundle)

    with pytest.raises(FileExistsError):
        init_app_manifest(workspace, write_manifest_input(tmp_path, second, "second.yaml"), bundle)


def test_init_force_replaces_existing_manifest(tmp_path, bundle) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    first = base_manifest()
    second = base_manifest()
    second["id"] = "replacement-app"
    init_app_manifest(workspace, write_manifest_input(tmp_path, first, "first.yaml"), bundle)

    result = init_app_manifest(
        workspace,
        write_manifest_input(tmp_path, second, "second.yaml"),
        bundle,
        force=True,
    )

    assert result["written"] is True
    validation = validate_manifest(workspace, bundle)
    assert validation["manifest_id"] == "replacement-app"


def test_render_manifest_excludes_documentation() -> None:
    manifest = base_manifest()
    manifest["documentation"] = {"model": "x", "config": {}}
    rendered = render_manifest(manifest)
    assert "documentation" not in rendered


def test_validate_manifest_fixture(bundle, tmp_path) -> None:
    workspace = tmp_path / "app"
    foundry_dir = workspace / ".foundry"
    foundry_dir.mkdir(parents=True)
    shutil.copy2(FIXTURE_APP, foundry_dir / "app.yaml")
    result = validate_manifest(workspace, bundle)
    assert result["ok"] is True
