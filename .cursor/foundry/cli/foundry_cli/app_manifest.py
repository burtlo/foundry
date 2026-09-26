"""Validate workspace .foundry/app.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from foundry_cli.errors import ok
from foundry_cli.validate import validate_payload


def manifest_path(workspace: Path) -> Path:
    return workspace / ".foundry" / "app.yaml"


def load_manifest(workspace: Path) -> tuple[Path, dict[str, Any]]:
    path = manifest_path(workspace)
    if not path.is_file():
        raise FileNotFoundError(f"Missing app manifest: {path}")
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("App manifest must be a mapping")
    return path, data


def validate_manifest(workspace: Path, foundry_bundle: Path) -> dict[str, Any]:
    path = manifest_path(workspace)
    if not path.is_file():
        return {"ok": False, "errors": [f"Missing app manifest: {path}"]}
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return {"ok": False, "errors": [f"Invalid YAML: {exc}"]}
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["App manifest must be a mapping"]}
    errors = validate_payload(data, "app-manifest.schema.json", foundry_bundle)
    if errors:
        return {"ok": False, "errors": errors, "manifest_id": data.get("id")}
    return ok(manifest_id=data.get("id"), errors=[])
