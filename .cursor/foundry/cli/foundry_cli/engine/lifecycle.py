"""Visit lifecycle: admission, transitions, and active visit tracking."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from foundry_cli.engine.hooks import run_hook, run_on_close
from foundry_cli.engine.routing import select_connection
from foundry_cli.ledger import append_event
from foundry_cli.registry import get_node
from foundry_cli.util import now_iso

RUN_UUID_KEY = "run_uuid"


def run_uuid(snapshot: dict[str, Any]) -> str:
    value = snapshot.get(RUN_UUID_KEY)
    if isinstance(value, str) and value:
        return value
    return str(snapshot.get("run_id") or "")


def next_visit_id(snapshot: dict[str, Any]) -> str:
    visits = snapshot.get("visits")
    max_num = 0
    if isinstance(visits, list):
        for visit in visits:
            if isinstance(visit, dict):
                match = re.fullmatch(r"v-(\d+)", str(visit.get("id", "")))
                if match:
                    max_num = max(max_num, int(match.group(1)))
    active = snapshot.get("active_visit")
    if isinstance(active, dict):
        match = re.fullmatch(r"v-(\d+)", str(active.get("id", "")))
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"v-{max_num + 1:03d}"


def generate_run_slug(workspace: Path, manifest_id: str | None) -> str:
    runs_dir = workspace / ".foundry" / "runs"
    prefix = manifest_id or "run"
    max_num = 0
    if runs_dir.is_dir():
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
        for child in runs_dir.iterdir():
            if child.is_dir():
                match = pattern.match(child.name)
                if match:
                    max_num = max(max_num, int(match.group(1)))
    return f"{prefix}-{max_num + 1:04d}"


def active_visit(snapshot: dict[str, Any]) -> dict[str, Any]:
    visit = snapshot.get("active_visit")
    if not isinstance(visit, dict):
        raise ValueError("snapshot has no active_visit")
    return visit


def update_active_visit(snapshot: dict[str, Any], visit: dict[str, Any]) -> None:
    snapshot["active_visit"] = visit
    visits = snapshot.setdefault("visits", [])
    if not isinstance(visits, list):
        visits = []
        snapshot["visits"] = visits
    for index, existing in enumerate(visits):
        if isinstance(existing, dict) and existing.get("id") == visit.get("id"):
            visits[index] = visit
            return
    visits.append(visit)


def admit_visit(
    snapshot: dict[str, Any],
    *,
    node_id: str,
    flow: dict[str, Any],
    source: str,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any]:
    node = get_node(flow, node_id)
    visit_id = next_visit_id(snapshot)
    visit = {
        "id": visit_id,
        "node_id": node_id,
        "kind": str(node.get("kind", "step")),
        "lifecycle": "admitted",
        "outcome": None,
        "decision": None,
    }
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="visit.admitted",
        visit_id=visit_id,
        node_id=node_id,
        payload={"source": source},
    )

    visit["lifecycle"] = "examined"
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="lifecycle.changed",
        visit_id=visit_id,
        node_id=node_id,
        payload={"from": "admitted", "to": "examined"},
    )

    examine_result = run_hook(
        snapshot,
        visit,
        flow,
        "on_examine",
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not examine_result["ok"]:
        action = examine_result.get("action", "halt")
        if action == "halt":
            snapshot["status"] = "halted"
            append_event(
                snapshot,
                event_type="run.status_changed",
                payload={"prior_status": "running", "new_status": "halted", "reason": examine_result.get("message")},
            )
        return visit

    open_result = run_hook(
        snapshot,
        visit,
        flow,
        "on_open",
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not open_result["ok"]:
        action = open_result.get("action", "halt")
        if action == "halt":
            prior = str(snapshot.get("status", "running"))
            snapshot["status"] = "halted"
            append_event(
                snapshot,
                event_type="run.status_changed",
                payload={"prior_status": prior, "new_status": "halted", "reason": open_result.get("message")},
            )
        return visit

    visit["lifecycle"] = "opened"
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="lifecycle.changed",
        visit_id=visit_id,
        node_id=node_id,
        payload={"from": "examined", "to": "opened"},
    )
    if str(node.get("kind")) == "gate":
        produces = node.get("produces") or {}
        options = produces.get("options") or []
        append_event(
            snapshot,
            event_type="gate.presented",
            visit_id=visit_id,
            node_id=node_id,
            payload={
                "options": list(options),
                "prompt": node.get("prompt"),
            },
        )
    return visit


def _seal_visit_and_route(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    visit_id = str(visit["id"])
    node_id = str(visit["node_id"])
    prior_lifecycle = str(visit["lifecycle"])

    close_result = run_on_close(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not close_result["ok"]:
        return {
            "ok": False,
            "code": close_result.get("code", "ARTIFACT_INCOMPLETE"),
            "message": close_result.get("message", "on_close checks failed"),
        }

    visit["lifecycle"] = "closed"
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="lifecycle.changed",
        visit_id=visit_id,
        node_id=node_id,
        payload={"from": "opened", "to": "closed"},
    )

    seal_result = run_hook(
        snapshot,
        visit,
        flow,
        "on_seal",
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not seal_result["ok"]:
        action = seal_result.get("action", "reopen")
        if action == "reopen":
            visit["lifecycle"] = "opened"
            if str(visit.get("kind")) == "gate":
                visit["decision"] = None
            update_active_visit(snapshot, visit)
            append_event(
                snapshot,
                event_type="lifecycle.changed",
                visit_id=visit_id,
                node_id=node_id,
                payload={"from": "closed", "to": "opened"},
            )
            return {
                "ok": False,
                "code": "CHECK_FAILED",
                "message": seal_result.get("message", "on_seal check failed"),
                "reopened": True,
                "visit_id": visit_id,
                "node_id": node_id,
                "prior_lifecycle": prior_lifecycle,
                "lifecycle": "opened",
                "policy": {"check": seal_result.get("check_id"), "action": "reopen"},
            }
        return {"ok": False, "code": "CHECK_FAILED", "message": seal_result.get("message", "on_seal failed")}

    visit["lifecycle"] = "sealed"
    visit["outcome"] = "completed"
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="lifecycle.changed",
        visit_id=visit_id,
        node_id=node_id,
        payload={"from": "closed", "to": "sealed"},
    )
    append_event(
        snapshot,
        event_type="visit.sealed",
        visit_id=visit_id,
        node_id=node_id,
        payload={"outcome": "completed", "summary": summary},
    )

    connection = select_connection(snapshot, node_id, flow, visit=visit)
    if connection is None:
        return {
            "ok": True,
            "visit_id": visit_id,
            "node_id": node_id,
            "prior_lifecycle": prior_lifecycle,
            "lifecycle": "sealed",
            "outcome": "completed",
            "connection": None,
        }

    connection_id = str(connection.get("id", ""))
    to_node_id = str(connection.get("to", ""))
    append_event(
        snapshot,
        event_type="connection.taken",
        visit_id=visit_id,
        node_id=node_id,
        payload={"connection_id": connection_id, "to_node_id": to_node_id},
    )

    next_visit = admit_visit(
        snapshot,
        node_id=to_node_id,
        flow=flow,
        source=connection_id,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )

    return {
        "ok": True,
        "visit_id": visit_id,
        "node_id": node_id,
        "prior_lifecycle": prior_lifecycle,
        "lifecycle": "sealed",
        "outcome": "completed",
        "connection": {"connection_id": connection_id, "to_node_id": to_node_id},
        "next_visit_id": next_visit.get("id"),
        "next_node_id": to_node_id,
        "next_lifecycle": next_visit.get("lifecycle"),
    }


def transition_visit(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    if str(visit.get("lifecycle")) != "opened":
        return {"ok": False, "code": "VISIT_NOT_OPENED", "message": f"Visit lifecycle is {visit.get('lifecycle')!r}, expected 'opened'"}

    if str(snapshot.get("status")) == "halted":
        return {"ok": False, "code": "RUN_HALTED", "message": "Run is halted"}

    if str(visit.get("kind")) == "gate":
        return {
            "ok": False,
            "code": "GATE_USE_DECIDE",
            "message": "Gate visits close via gate decide, not visit transition",
        }

    return _seal_visit_and_route(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary,
    )
