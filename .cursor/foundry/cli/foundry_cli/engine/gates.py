"""Gate decision handling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.engine.lifecycle import _seal_visit_and_route, update_active_visit
from foundry_cli.ledger import append_event
from foundry_cli.registry import get_node


def decide_gate(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    decision: str,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any]:
    if str(visit.get("lifecycle")) != "opened":
        return {
            "ok": False,
            "code": "VISIT_NOT_OPENED",
            "message": f"Visit lifecycle is {visit.get('lifecycle')!r}, expected 'opened'",
        }

    if str(snapshot.get("status")) == "halted":
        return {"ok": False, "code": "RUN_HALTED", "message": "Run is halted"}

    if str(visit.get("kind")) != "gate":
        return {
            "ok": False,
            "code": "CAPABILITY_DENIED",
            "message": f"gate decide is not allowed on step node {visit.get('node_id')!r}",
        }

    node_id = str(visit["node_id"])
    node = get_node(flow, node_id)
    allow = node.get("allow") or {}
    user = allow.get("user") if isinstance(allow.get("user"), dict) else {}
    if not user.get("decide"):
        return {
            "ok": False,
            "code": "GATE_DECIDE_DENIED",
            "message": f"Gate {node_id!r} does not allow user decide",
        }

    if str(node.get("decider")) != "user":
        return {
            "ok": False,
            "code": "GATE_DECIDE_DENIED",
            "message": f"Gate {node_id!r} is not a user gate (decider: {node.get('decider')!r})",
        }

    produces = node.get("produces") or {}
    options = [str(item) for item in (produces.get("options") or [])]
    if decision not in options:
        return {
            "ok": False,
            "code": "INVALID_GATE_DECISION",
            "message": f"Decision {decision!r} not in gate options: {options}",
            "options": options,
        }

    visit_id = str(visit["id"])
    visit["decision"] = decision
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="gate.resolved",
        visit_id=visit_id,
        node_id=node_id,
        payload={"decision": decision},
    )

    result = _seal_visit_and_route(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if result.get("ok"):
        result["decision"] = decision
    return result
