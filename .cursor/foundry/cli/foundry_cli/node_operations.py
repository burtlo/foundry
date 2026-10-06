"""Load node operations manifests (deterministic workflow steps)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from foundry_cli.paths import resolve_registry_path


def load_operations_text(registry_ref: str, foundry_bundle: Path) -> str:
    """Read operations YAML referenced from factory-flow (registry:nodes/.../operations.yaml)."""
    path = resolve_registry_path(registry_ref, foundry_bundle)
    return path.read_text(encoding="utf-8")


def load_operations(registry_ref: str, foundry_bundle: Path) -> dict[str, Any]:
    text = load_operations_text(registry_ref, foundry_bundle)
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Operations manifest must be a mapping: {registry_ref}")
    return data
