"""Worker packet redaction and size enforcement."""

from __future__ import annotations

import json
import re
from typing import Any


SENSITIVE_KEY_RE = re.compile(
    r"(^|_)(password|passwd|api_key|access_token|refresh_token|client_secret|connection_string)$",
    re.IGNORECASE,
)


class ContextError(Exception):
    def __init__(self, error_code: str, message: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.extra = extra or {}


def redact(value: Any, path: str = "") -> tuple[Any, list[str]]:
    redacted_paths: list[str] = []
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            dotted = f"{path}.{key}" if path else str(key)
            if SENSITIVE_KEY_RE.search(str(key)):
                result[key] = "[REDACTED]"
                redacted_paths.append(dotted)
            else:
                result[key], nested = redact(item, dotted)
                redacted_paths.extend(nested)
        return result, redacted_paths
    if isinstance(value, list):
        result_list: list[Any] = []
        for index, item in enumerate(value):
            redacted, nested = redact(item, f"{path}[{index}]")
            result_list.append(redacted)
            redacted_paths.extend(nested)
        return result_list, redacted_paths
    return value, redacted_paths


def encoded_chars(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def enforce_packet(packet: dict[str, Any], budget: dict[str, Any]) -> dict[str, int]:
    actual = encoded_chars(packet)
    maximum = int(budget["max_input_chars"])
    if actual > maximum:
        raise ContextError(
            "WORKER_CONTEXT_BUDGET_EXCEEDED",
            f"Worker packet is {actual} characters; budget is {maximum}.",
            extra={"actual": actual, "budget": maximum},
        )
    return {
        "packet_chars": actual,
        "max_input_chars": maximum,
        "utilization_percent": round((actual / maximum) * 100),
    }


def enforce_summary(craft: dict[str, Any], budget: dict[str, Any]) -> int:
    outputs = craft.get("outputs") if isinstance(craft.get("outputs"), dict) else {}
    summary = outputs.get("summary_markdown")
    actual = len(summary) if isinstance(summary, str) else 0
    maximum = int(budget["max_summary_chars"])
    if actual > maximum:
        raise ContextError(
            "WORKER_SUMMARY_BUDGET_EXCEEDED",
            f"Worker summary is {actual} characters; budget is {maximum}.",
            extra={"actual": actual, "budget": maximum},
        )
    return actual
