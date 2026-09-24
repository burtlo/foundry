"""Idempotency helpers for Foundry external operations."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


def request_digest(request: dict[str, Any]) -> str:
    encoded = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def operation_id(
    *,
    run_id: str,
    integration: str,
    operation: str,
    target: str,
    request: dict[str, Any],
) -> str:
    digest = request_digest(request)
    return str(uuid.uuid5(uuid.UUID(run_id), f"{integration}:{operation}:{target}:{digest}"))


def matching_operations(events: list[dict[str, Any]], operation_id_value: str) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("event_type") == "external_operation"
        and isinstance(event.get("payload"), dict)
        and event["payload"].get("operation_id") == operation_id_value
    ]


def latest_success(events: list[dict[str, Any]], operation_id_value: str) -> dict[str, Any] | None:
    for event in reversed(matching_operations(events, operation_id_value)):
        status = (event.get("payload") or {}).get("status")
        if status in ("succeeded", "reconciled"):
            return event
    return None


def next_attempt(events: list[dict[str, Any]], operation_id_value: str) -> int:
    attempts = [
        int((event.get("payload") or {}).get("attempt") or 0)
        for event in matching_operations(events, operation_id_value)
    ]
    return max(attempts, default=0) + 1
