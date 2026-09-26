"""Validate workspace .foundry/app.yaml."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from foundry_cli.validate import validate_payload


def manifest_path(workspace: Path) -> Path:
    return workspace / ".foundry" / "app.yaml"


def load_manifest(workspace: Path) -> tuple[dict[str, Any] | None, list[str]]:
    path = manifest_path(workspace)
    if not path.is_file():
        return None, [f"Missing app manifest: {path}"]
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return None, [f"Invalid YAML in {path}: {exc}"]
    if not isinstance(data, dict):
        return None, [f"App manifest must be a mapping: {path}"]
    schema_errors = validate_payload(data, "app-manifest.schema.json", _bundle_from_workspace(workspace))
    return data, schema_errors


def _bundle_from_workspace(workspace: Path) -> Path:
    from foundry_cli.paths import foundry_root

    return foundry_root(workspace)


def validate_manifest(workspace: Path, foundry_bundle: Path) -> dict[str, Any]:
    path = manifest_path(workspace)
    if not path.is_file():
        return {"passed": False, "errors": [f"Missing app manifest: {path}"]}
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return {"passed": False, "errors": [f"Invalid YAML: {exc}"]}
    if not isinstance(data, dict):
        return {"passed": False, "errors": ["App manifest must be a mapping"]}
    errors = validate_payload(data, "app-manifest.schema.json", foundry_bundle)
    if errors:
        return {"passed": False, "errors": errors, "manifest_id": data.get("id")}
    return {"passed": True, "errors": [], "manifest_id": data.get("id")}
