"""Append-only ledger stored inline in snapshot.json; durable commits sync ledger.jsonl."""

from __future__ import annotations

from typing import Any

from foundry_cli.util import now_iso


def ledger_events(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    ledger = snapshot.get("ledger")
    if ledger is None:
        return []
    if not isinstance(ledger, list):
        raise ValueError("snapshot.ledger must be a list")
    return ledger


def next_seq(snapshot: dict[str, Any]) -> int:
    events = ledger_events(snapshot)
    if not events:
        return 1
    return max(int(event.get("seq", 0)) for event in events if isinstance(event, dict)) + 1


def append_event(
    snapshot: dict[str, Any],
    *,
    event_type: str,
    visit_id: str | None = None,
    node_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "seq": next_seq(snapshot),
        "visit_id": visit_id,
        "node_id": node_id,
        "type": event_type,
        "payload": payload or {},
    }
    if "at" not in event:
        event["at"] = now_iso()
    ledger = snapshot.setdefault("ledger", [])
    if not isinstance(ledger, list):
        raise ValueError("snapshot.ledger must be a list")
    ledger.append(event)
    return event


def filter_events(
    snapshot: dict[str, Any],
    *,
    from_seq: int | None = None,
    to_seq: int | None = None,
    types: list[str] | None = None,
) -> list[dict[str, Any]]:
    events = ledger_events(snapshot)
    filtered: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        seq = int(event.get("seq", 0))
        if from_seq is not None and seq < from_seq:
            continue
        if to_seq is not None and seq > to_seq:
            continue
        if types and str(event.get("type")) not in types:
            continue
        filtered.append(event)
    return filtered


def count_events(
    snapshot: dict[str, Any],
    event_type: str,
    *,
    visit_id: str | None = None,
    node_id: str | None = None,
    schema: str | None = None,
    loop: str | None = None,
) -> int:
    count = 0
    for event in ledger_events(snapshot):
        if not isinstance(event, dict) or event.get("type") != event_type:
            continue
        if visit_id is not None and event.get("visit_id") != visit_id:
            continue
        if node_id is not None and event.get("node_id") != node_id:
            continue
        payload = event.get("payload") or {}
        if schema is not None and payload.get("schema") != schema:
            continue
        if loop is not None and payload.get("loop") != loop:
            continue
        count += 1
    return count


def last_event(
    snapshot: dict[str, Any],
    event_type: str,
    *,
    node_id: str | None = None,
    visit_id: str | None = None,
) -> dict[str, Any] | None:
    matches = [
        event
        for event in ledger_events(snapshot)
        if isinstance(event, dict)
        and event.get("type") == event_type
        and (node_id is None or event.get("node_id") == node_id)
        and (visit_id is None or event.get("visit_id") == visit_id)
    ]
    return matches[-1] if matches else None


def has_artifact_linked(snapshot: dict[str, Any], *, visit_id: str, artifact_id: str) -> bool:
    for event in ledger_events(snapshot):
        if not isinstance(event, dict) or event.get("type") != "artifact.linked":
            continue
        if event.get("visit_id") != visit_id:
            continue
        payload = event.get("payload") or {}
        if payload.get("artifact_id") == artifact_id:
            return True
    return False
