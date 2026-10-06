"""Materialize run snapshot state from ledger checkpoints and event replay."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from foundry_cli.engine.lifecycle import RUN_UUID_KEY, update_active_visit
from foundry_cli.ledger import next_seq

CHECKPOINT_EVENT_TYPE = "run.snapshot.checkpoint"

MATERIALIZED_TOP_LEVEL_KEYS = (
    "schema_version",
    "run_id",
    RUN_UUID_KEY,
    "flow_id",
    "status",
    "workspace",
    "config",
    "state",
    "visits",
    "active_visit",
    "wait",
    "agent_requests",
    "revision",
)


def build_checkpoint_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in MATERIALIZED_TOP_LEVEL_KEYS:
        if key in snapshot:
            payload[key] = deepcopy(snapshot[key])
    return payload


def apply_checkpoint_payload(snapshot: dict[str, Any], payload: dict[str, Any]) -> None:
    for key in MATERIALIZED_TOP_LEVEL_KEYS:
        if key in payload:
            snapshot[key] = deepcopy(payload[key])


def is_runnable_snapshot(snapshot: dict[str, Any]) -> bool:
    run_id = snapshot.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return False
    active = snapshot.get("active_visit")
    if not isinstance(active, dict) or not active.get("id"):
        return False
    status = snapshot.get("status")
    if not isinstance(status, str) or not status.strip():
        return False
    return True


def _find_visit(snapshot: dict[str, Any], visit_id: str) -> dict[str, Any] | None:
    active = snapshot.get("active_visit")
    if isinstance(active, dict) and str(active.get("id")) == visit_id:
        return active
    visits = snapshot.get("visits")
    if isinstance(visits, list):
        for visit in visits:
            if isinstance(visit, dict) and str(visit.get("id")) == visit_id:
                return visit
    return None


def _agent_requests(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw = snapshot.get("agent_requests")
    if not isinstance(raw, dict):
        raw = {}
        snapshot["agent_requests"] = raw
    return raw


def _apply_event(snapshot: dict[str, Any], event: dict[str, Any]) -> None:
    event_type = str(event.get("type") or "")
    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    visit_id = event.get("visit_id")
    node_id = event.get("node_id")

    if event_type == "run.status_changed":
        new_status = payload.get("new_status")
        if isinstance(new_status, str):
            snapshot["status"] = new_status
        return

    if event_type == "visit.admitted":
        if not isinstance(visit_id, str):
            return
        visit = {
            "id": visit_id,
            "node_id": str(node_id or payload.get("node_id") or ""),
            "kind": str(payload.get("kind") or "step"),
            "lifecycle": "admitted",
            "outcome": None,
            "decision": None,
        }
        update_active_visit(snapshot, visit)
        return

    if event_type == "lifecycle.changed":
        if not isinstance(visit_id, str):
            return
        visit = _find_visit(snapshot, visit_id)
        if visit is None:
            return
        to_lifecycle = payload.get("to")
        if isinstance(to_lifecycle, str):
            visit["lifecycle"] = to_lifecycle
            update_active_visit(snapshot, visit)
        return

    if event_type == "gate.resolved":
        if not isinstance(visit_id, str):
            return
        visit = _find_visit(snapshot, visit_id)
        if visit is None:
            return
        decision = payload.get("decision")
        if decision is not None:
            visit["decision"] = str(decision)
            update_active_visit(snapshot, visit)
        return

    if event_type == "agent.requested":
        request_id = payload.get("request_id")
        if not isinstance(request_id, str):
            return
        record = _agent_requests(snapshot).setdefault(
            request_id,
            {
                "request_id": request_id,
                "visit_id": visit_id,
                "task_id": payload.get("task_id"),
                "status": "requested",
                "attempt": payload.get("attempt"),
                "definition_digest": payload.get("definition_digest"),
                "input_digest": payload.get("input_digest"),
            },
        )
        if isinstance(record, dict):
            record["status"] = record.get("status") or "requested"
        return

    if event_type == "agent.dispatch.outbox":
        request_id = payload.get("request_id")
        if not isinstance(request_id, str):
            return
        record = _agent_requests(snapshot).get(request_id)
        if isinstance(record, dict):
            record["dispatch_outbox"] = {"status": payload.get("status") or "pending", "request_id": request_id}
        return

    if event_type == "agent.dispatched":
        request_id = payload.get("request_id")
        if not isinstance(request_id, str):
            return
        record = _agent_requests(snapshot).get(request_id)
        if isinstance(record, dict):
            record["status"] = "dispatched"
            if payload.get("provider_request_id") is not None:
                record["provider_request_id"] = payload.get("provider_request_id")
            if payload.get("finish_reason") is not None:
                record["finish_reason"] = payload.get("finish_reason")
        return

    if event_type == "agent.result.accepted":
        request_id = payload.get("request_id")
        if not isinstance(request_id, str):
            return
        record = _agent_requests(snapshot).get(request_id)
        if isinstance(record, dict):
            record["status"] = "accepted"
        state = snapshot.setdefault("state", {})
        if isinstance(state, dict) and isinstance(payload.get("state_patch"), dict):
            state.update(deepcopy(payload["state_patch"]))
        return

    if event_type == CHECKPOINT_EVENT_TYPE:
        materialized = payload.get("materialized")
        if isinstance(materialized, dict):
            apply_checkpoint_payload(snapshot, materialized)
        return


def materialize_snapshot_from_ledger(
    events: list[dict[str, Any]],
    partial: dict[str, Any] | None,
) -> dict[str, Any]:
    """Rebuild snapshot fields from checkpoints plus replay of trailing events."""
    base: dict[str, Any] = dict(partial) if isinstance(partial, dict) else {}
    base.setdefault("ledger", list(events))
    base.setdefault("agent_requests", {})
    base.setdefault("visits", [])
    base.setdefault("state", {})
    base.setdefault("config", {})
    base.setdefault("wait", None)

    last_checkpoint_seq = 0
    for event in events:
        if isinstance(event, dict) and event.get("type") == CHECKPOINT_EVENT_TYPE:
            materialized = (event.get("payload") or {}).get("materialized")
            if isinstance(materialized, dict):
                apply_checkpoint_payload(base, materialized)
                last_checkpoint_seq = int(event.get("seq", 0))

    for event in events:
        if not isinstance(event, dict):
            continue
        if int(event.get("seq", 0)) <= last_checkpoint_seq:
            continue
        if event.get("type") == CHECKPOINT_EVENT_TYPE:
            continue
        _apply_event(base, event)

    base["ledger"] = list(events)
    if base.get("revision") is None:
        rev = 0
        for event in events:
            if event.get("type") == CHECKPOINT_EVENT_TYPE:
                materialized = (event.get("payload") or {}).get("materialized")
                if isinstance(materialized, dict) and materialized.get("revision") is not None:
                    rev = int(materialized["revision"])
        base["revision"] = rev
    return base


def append_checkpoint_event(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Append an in-memory checkpoint event (caller persists via commit_snapshot)."""
    event = {
        "seq": next_seq(snapshot),
        "type": CHECKPOINT_EVENT_TYPE,
        "payload": {"materialized": build_checkpoint_payload(snapshot)},
    }
    ledger = snapshot.setdefault("ledger", [])
    if not isinstance(ledger, list):
        raise ValueError("snapshot.ledger must be a list")
    ledger.append(event)
    return event
