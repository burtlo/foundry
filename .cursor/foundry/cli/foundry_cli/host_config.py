"""Load operator host settings from .foundry/host.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from foundry_cli.validate import validate_payload

HOST_CONFIG_SCHEMA_VERSION = 1


def host_config_path(workspace: Path) -> Path:
    return workspace.resolve() / ".foundry" / "host.yaml"


def load_host_config(workspace: Path | None, *, bundle: Path | None = None) -> dict[str, Any]:
    """Return parsed host config or {} when missing. Invalid YAML returns {}."""
    if workspace is None:
        return {}
    path = host_config_path(workspace)
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    if bundle is not None:
        errors = validate_payload(data, "host-config.schema.json", bundle.resolve())
        if errors:
            return {}
    return data


def advance_client_section(host_config: dict[str, Any]) -> dict[str, Any]:
    section = host_config.get("advance_client")
    return section if isinstance(section, dict) else {}
