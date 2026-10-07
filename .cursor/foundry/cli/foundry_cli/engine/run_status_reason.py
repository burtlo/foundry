"""Typed halt / pause reasons on run snapshots (G8)."""

from __future__ import annotations

from typing import Any

FLOW_CHECK_HALT_CODES: dict[str, str] = {
    "repair-within-limit": "REPAIR_LIMIT_EXCEEDED",
    "reverify-within-limit": "REVERIFY_LIMIT_EXCEEDED",
}

# Operator may call retry_run / foundry retry when these codes are set (paused or halted).
RETRY_ELIGIBLE_HALT_CODES: frozenset[str] = frozenset(
    {
        "REPAIR_LIMIT_EXCEEDED",
        "REVERIFY_LIMIT_EXCEEDED",
        "EVIDENCE_MISSING",
        "EVIDENCE_CONFLICT",
        "ENGINE_GATE_STUB",
    }
)


def halt_code_for_flow_check(check_id: str) -> str | None:
    return FLOW_CHECK_HALT_CODES.get(check_id)


def set_status_reason(
    snapshot: dict[str, Any],
    code: str,
    *,
    message: str | None = None,
) -> None:
    """Record typed reason on snapshot for status / attach reads."""
    text = (message or "").strip() or code
    retry_eligible = code in RETRY_ELIGIBLE_HALT_CODES
    snapshot["status_reason"] = {
        "code": code,
        "message": text,
        "retry_eligible": retry_eligible,
    }
    snapshot["halt_reason"] = code


def clear_status_reason(snapshot: dict[str, Any]) -> None:
    snapshot.pop("status_reason", None)
    snapshot.pop("halt_reason", None)


def status_reason_payload(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    raw = snapshot.get("status_reason")
    if isinstance(raw, dict) and raw.get("code"):
        return raw
    code = snapshot.get("halt_reason")
    if isinstance(code, str) and code.strip():
        return {
            "code": code.strip(),
            "message": code.strip(),
            "retry_eligible": code.strip() in RETRY_ELIGIBLE_HALT_CODES,
        }
    return None
