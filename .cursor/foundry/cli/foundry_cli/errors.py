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


def from_engine_result(result: dict[str, Any]) -> dict[str, Any]:
    """Convert engine result to command envelope."""
    if result.get("ok"):
        return ok(**{k: v for k, v in result.items() if k != "ok"})
    return error(
        str(result.get("code", "ENGINE_ERROR")),
        str(result.get("message", "Operation failed")),
        **{k: v for k, v in result.items() if k not in {"ok", "code", "message"}},
    )
