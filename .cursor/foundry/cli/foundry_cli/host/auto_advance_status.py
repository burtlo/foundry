"""Persist auto-advance daemon telemetry for ``foundry host status``."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from foundry_cli.host.discovery import restrict_host_dir_permissions
from foundry_cli.host.paths import auto_advance_status_path, host_dir
from foundry_cli.util import now_iso

_MAX_FAILURES = 20


def read_auto_advance_status(workspace: Path) -> dict[str, Any] | None:
    path = auto_advance_status_path(workspace)
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def write_auto_advance_status(workspace: Path, payload: dict[str, Any]) -> None:
    workspace = workspace.resolve()
    restrict_host_dir_permissions(host_dir(workspace))
    path = auto_advance_status_path(workspace)
    body = {**payload, "updated_at": now_iso()}
    temp = path.with_suffix(".json.tmp")
    text = json.dumps(body, indent=2, sort_keys=True) + "\n"
    with temp.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def clear_auto_advance_status(workspace: Path) -> None:
    path = auto_advance_status_path(workspace)
    if path.is_file():
        path.unlink()


def merge_failures(
    prior: list[dict[str, Any]] | None,
    new_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    combined = list(prior or []) + list(new_items)
    return combined[-_MAX_FAILURES:]
