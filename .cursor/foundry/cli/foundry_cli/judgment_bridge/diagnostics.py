"""Structured judgment / bridge error payloads."""

from __future__ import annotations

from typing import Any


class JudgmentAdapterFailure(Exception):
    """HTTP judgment adapter failed; carries structured CLI diagnostics."""

    def __init__(
        self,
        message: str,
        *,
        diagnostics: dict[str, Any],
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics
        self.http_status = http_status


def bridge_error_body(
    *,
    layer: str,
    message: str,
    hint: str,
    upstream_status: int | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": message,
        "diagnostics": {
            "layer": layer,
            "recovery_hint": hint,
            "upstream_status": upstream_status,
            "code": code,
        },
    }
