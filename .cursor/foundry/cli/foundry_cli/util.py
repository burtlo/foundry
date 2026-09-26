"""Shared utility helpers for Foundry CLI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def list_or_empty(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("Expected list")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
