"""Unit tests for foundry_cli.app_manifest."""

from __future__ import annotations

import shutil

import pytest
import yaml

from foundry_cli.app_manifest import validate_manifest
from tests.conftest import FOUNDRY_ROOT

FIXTURE_APP = FOUNDRY_ROOT / "fixtures" / "apps" / "foundry-test" / ".foundry" / "app.yaml"


@pytest.fixture
def workspace_with_manifest(tmp_path, bundle):
    foundry_dir = tmp_path / ".foundry"
    foundry_dir.mkdir()
    shutil.copy2(FIXTURE_APP, foundry_dir / "app.yaml")
    return tmp_path


def test_validate_manifest_success(workspace_with_manifest, bundle) -> None:
    result = validate_manifest(workspace_with_manifest, bundle)
    assert result["ok"] is True
    assert result["errors"] == []
    assert result["manifest_id"] == "foundry-test"


def test_validate_manifest_missing_file(tmp_path, bundle) -> None:
    result = validate_manifest(tmp_path, bundle)
    assert result["ok"] is False
    assert result["errors"]
    assert "Missing app manifest" in result["errors"][0]


def test_validate_manifest_invalid_yaml(tmp_path, bundle) -> None:
    foundry_dir = tmp_path / ".foundry"
    foundry_dir.mkdir()
    (foundry_dir / "app.yaml").write_text("id: [unclosed", encoding="utf-8")
    result = validate_manifest(tmp_path, bundle)
    assert result["ok"] is False
    assert any("Invalid YAML" in error for error in result["errors"])


def test_validate_manifest_schema_errors(tmp_path, bundle) -> None:
    foundry_dir = tmp_path / ".foundry"
    foundry_dir.mkdir()
    with (foundry_dir / "app.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump({"id": "broken"}, handle)
    result = validate_manifest(tmp_path, bundle)
    assert result["ok"] is False
    assert result["errors"]
    assert result.get("manifest_id") == "broken"
