"""CLI response envelopes."""

from __future__ import annotations

from typing import Any


def ok(**fields: Any) -> dict[str, Any]:
    return {"ok": True, **fields}


def error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "error": {"code": code, "message": message}}
    if extra:
        payload.update(extra)
    return payload
