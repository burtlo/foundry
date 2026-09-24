"""Cursor session and usage telemetry for Foundry eval runs."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

import foundry_protocol


class CursorTelemetryError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.extra = extra or {}


def write_cursor_session(
    run_dir: Path,
    *,
    conversation_id: str,
    started_at: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": foundry_protocol.PROTOCOL_VERSION,
        "conversation_id": conversation_id,
        "started_at": started_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if extra:
        payload.update(extra)
    path = run_dir / "cursor-session.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"path": str(path), "session": payload}


def append_tool_event(
    run_dir: Path,
    event: dict[str, Any],
) -> str:
    path = run_dir / "cursor-telemetry.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    return str(path)


def fetch_filtered_usage_events(
    *,
    api_key: str,
    start_date: str,
    end_date: str,
    email: str | None = None,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    body: dict[str, Any] = {
        "startDate": start_date,
        "endDate": end_date,
        "pageSize": page_size,
    }
    if email:
        body["email"] = email
    encoded = json.dumps(body).encode("utf-8")
    req = request.Request(
        "https://api.cursor.com/teams/filtered-usage-events",
        data=encoded,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CursorTelemetryError(
            "CURSOR_API_HTTP_ERROR",
            f"Cursor Admin API returned HTTP {exc.code}.",
            extra={"body": detail},
        ) from exc
    except error.URLError as exc:
        raise CursorTelemetryError(
            "CURSOR_API_UNREACHABLE",
            f"Could not reach Cursor Admin API: {exc.reason}",
        ) from exc

    events = payload.get("usageEvents") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        return []
    return [item for item in events if isinstance(item, dict)]


def summarize_usage_for_conversation(
    events: list[dict[str, Any]],
    conversation_ids: list[str],
) -> dict[str, Any]:
    wanted = {item for item in conversation_ids if item}
    matched: list[dict[str, Any]] = []
    for event in events:
        conversation_id = event.get("conversationId") or event.get("conversation_id")
        if isinstance(conversation_id, str) and conversation_id in wanted:
            matched.append(event)

    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    charged_cents = 0.0
    request_count = 0
    by_model: dict[str, int] = {}

    for event in matched:
        request_count += 1
        token_usage = event.get("tokenUsage") if isinstance(event.get("tokenUsage"), dict) else {}
        input_tokens += int(token_usage.get("inputTokens") or 0)
        output_tokens += int(token_usage.get("outputTokens") or 0)
        cache_read_tokens += int(token_usage.get("cacheReadTokens") or 0)
        charged = event.get("chargedCents")
        if charged is None and isinstance(token_usage.get("totalCents"), (int, float)):
            charged = token_usage.get("totalCents")
        if isinstance(charged, (int, float)):
            charged_cents += float(charged)
        model = event.get("model")
        if isinstance(model, str):
            by_model[model] = by_model.get(model, 0) + 1

    return {
        "conversation_ids": sorted(wanted),
        "request_count": request_count,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "charged_cents": round(charged_cents, 4),
        "by_model": by_model,
        "events_matched": len(matched),
    }


def enrich_cursor_usage(
    run_dir: Path,
    *,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    email: str | None = None,
    conversation_ids: list[str] | None = None,
) -> dict[str, Any]:
    session_path = run_dir / "cursor-session.json"
    if not session_path.is_file():
        raise CursorTelemetryError(
            "MISSING_CURSOR_SESSION",
            f"cursor-session.json not found in {run_dir}",
        )
    session = json.loads(session_path.read_text(encoding="utf-8"))
    if not isinstance(session, dict):
        raise CursorTelemetryError("INVALID_CURSOR_SESSION", "cursor-session.json must be a JSON object.")

    ids = conversation_ids or []
    primary = session.get("conversation_id")
    if isinstance(primary, str) and primary not in ids:
        ids.append(primary)
    extra_ids = session.get("conversation_ids")
    if isinstance(extra_ids, list):
        for item in extra_ids:
            if isinstance(item, str) and item not in ids:
                ids.append(item)
    if not ids:
        raise CursorTelemetryError(
            "MISSING_CONVERSATION_ID",
            "No conversation_id available in cursor-session.json.",
        )

    resolved_key = api_key or os.environ.get("CURSOR_ADMIN_API_KEY")
    if not resolved_key:
        raise CursorTelemetryError(
            "MISSING_API_KEY",
            "Set CURSOR_ADMIN_API_KEY or pass --api-key for usage enrichment.",
        )

    started_at = session.get("started_at")
    completed_at = session.get("completed_at")
    resolved_start = start_date or (str(started_at)[:10] if isinstance(started_at, str) else None)
    resolved_end = end_date or (str(completed_at)[:10] if isinstance(completed_at, str) else None)
    if not resolved_start or not resolved_end:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        resolved_start = resolved_start or today
        resolved_end = resolved_end or today

    events = fetch_filtered_usage_events(
        api_key=resolved_key,
        start_date=resolved_start,
        end_date=resolved_end,
        email=email or session.get("email"),
    )
    usage = summarize_usage_for_conversation(events, ids)
    payload = {
        "schema_version": foundry_protocol.PROTOCOL_VERSION,
        "artifact": "cursor-usage",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": {"start_date": resolved_start, "end_date": resolved_end},
        "usage": usage,
    }
    output_path = run_dir / "cursor-usage.json"
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"path": str(output_path), "usage": payload}
