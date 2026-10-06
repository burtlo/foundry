"""Gate decision handling and engine gate resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from foundry_cli.engine.hooks import _load_agent_receipt_for_visit, _latest_sealed_visit_id
from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
from foundry_cli.engine.lifecycle import _seal_visit_and_route, update_active_visit
from foundry_cli.engine.routing import _config_limit
from foundry_cli.ledger import append_event, count_events, ledger_events
from foundry_cli.paths import resolve_run_uri
from foundry_cli.registry import get_node

AGENT_RECEIPT_SCHEMA = "registry:schemas/agent-receipt.schema.json"

# Engine gates without a resolver remain stubs until their workflow slice lands.
ENGINE_GATE_STUBS: frozenset[str] = frozenset(
    {
        "execute.commit.gate",
        "verify.intake.gate",
        "verify.acceptance.gate",
        "verify.code_quality.gate",
        "verify.code_review.gate",
        "verify.complete.gate",
    }
)


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

    if str(node.get("decider")) == "engine":
        return {
            "ok": False,
            "code": "CAPABILITY_DENIED",
            "message": f"Gate {node_id!r} is resolved by the engine, not user gate decide",
        }

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
        payload={"decision": decision, "decider": "user"},
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


def _load_intake_receipt_for_visit(
    snapshot: dict[str, Any],
    visit_id: str,
    run_dir: Path,
) -> dict[str, Any] | None:
    for event in reversed(ledger_events(snapshot)):
        if not isinstance(event, dict) or event.get("type") != "receipt.linked":
            continue
        if event.get("visit_id") != visit_id:
            continue
        payload = event.get("payload") or {}
        if payload.get("schema") != INTAKE_RECEIPT_SCHEMA:
            continue
        path_uri = payload.get("path")
        if not isinstance(path_uri, str):
            return None
        receipt_path = resolve_run_uri(path_uri, run_dir, visit_id)
        if not receipt_path.is_file():
            return {"_missing_file": str(receipt_path)}
        return json.loads(receipt_path.read_text(encoding="utf-8"))
    return None


def _execute_intake_gate_decision(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    intake_visit_id = _latest_sealed_visit_id(snapshot, "execute.intake")
    if not intake_visit_id:
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": "execute.intake visit is not sealed",
        }

    receipt = _load_intake_receipt_for_visit(snapshot, intake_visit_id, run_dir)
    if receipt is None:
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": "No intake receipt linked for sealed execute.intake visit",
        }
    if receipt.get("_missing_file"):
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": f"Intake receipt file missing: {receipt['_missing_file']}",
        }

    receipt_id = receipt.get("receipt_id")
    evidence_refs = [str(receipt_id)] if receipt_id else []
    status = str(receipt.get("status") or "")
    if status == "passed":
        return {
            "ok": True,
            "decision": "pass",
            "rule_id": "execute.intake.gate/intake-passed",
            "evidence_refs": evidence_refs,
        }
    if status in ("blocked", "failed"):
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": f"Execute intake receipt status is {status!r}; gate cannot pass",
            "evidence_refs": evidence_refs,
        }
    return {
        "ok": False,
        "code": "EVIDENCE_MISSING",
        "message": "Execute intake receipt did not yield a pass signal",
        "evidence_refs": evidence_refs,
    }


def _execute_test_gate_decision(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    """Map sealed execute.test agent receipt to pass | repair."""
    test_visit_id = _latest_sealed_visit_id(snapshot, "execute.test")
    if not test_visit_id:
        return {"ok": False, "code": "EVIDENCE_MISSING", "message": "execute.test visit is not sealed"}

    receipt = _load_agent_receipt_for_visit(snapshot, test_visit_id, run_dir)
    if receipt is None:
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": "No agent receipt linked for sealed execute.test visit",
        }
    if receipt.get("_missing_file"):
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": f"Agent receipt file missing: {receipt['_missing_file']}",
        }

    receipt_id = receipt.get("receipt_id")
    evidence_refs = [str(receipt_id)] if receipt_id else []

    pass_signal = False
    repair_signal = False

    status = receipt.get("status")
    commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []

    if commands:
        if all(isinstance(item, dict) and item.get("exit_code", 1) == 0 for item in commands):
            pass_signal = True
        if any(isinstance(item, dict) and item.get("exit_code", 0) != 0 for item in commands):
            repair_signal = True
    elif status == "completed":
        pass_signal = True
    elif status in ("failed", "partial"):
        repair_signal = True

    if pass_signal and repair_signal:
        return {
            "ok": False,
            "code": "EVIDENCE_CONFLICT",
            "message": "Conflicting test evidence: pass and repair signals both present",
            "evidence_refs": evidence_refs,
        }

    if pass_signal:
        return {
            "ok": True,
            "decision": "pass",
            "rule_id": "execute.test.gate/receipt-pass",
            "evidence_refs": evidence_refs,
        }
    if repair_signal:
        return {
            "ok": True,
            "decision": "repair",
            "rule_id": "execute.test.gate/receipt-repair",
            "evidence_refs": evidence_refs,
        }

    return {
        "ok": False,
        "code": "EVIDENCE_MISSING",
        "message": "execute.test receipt did not yield pass or repair signals",
        "evidence_refs": evidence_refs,
    }


def _execute_repair_limit_gate_decision(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    """Allow proceed when repair loop count is within config.limits.repair."""
    repair_count = count_events(snapshot, "connection.taken", loop="repair")
    limit = _config_limit(snapshot, "repair", 2)
    if repair_count > limit:
        return {
            "ok": False,
            "code": "REPAIR_LIMIT_EXCEEDED",
            "message": (
                f"Repair loop count {repair_count} exceeds configured limit {limit}"
            ),
        }
    return {
        "ok": True,
        "decision": "proceed",
        "rule_id": "execute.repair.limit.gate/proceed",
        "evidence_refs": [],
    }


_ENGINE_RESOLVERS: dict[str, Callable[..., dict[str, Any]]] = {
    "execute.intake.gate": _execute_intake_gate_decision,
    "execute.test.gate": _execute_test_gate_decision,
    "execute.repair.limit.gate": _execute_repair_limit_gate_decision,
}


def resolve_engine_gate_decision(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    node_id = str(visit["node_id"])
    node = get_node(flow, node_id)
    if str(node.get("decider")) != "engine":
        return {"ok": False, "code": "NOT_ENGINE_GATE", "message": f"{node_id} is not an engine gate"}

    resolver = _ENGINE_RESOLVERS.get(node_id)
    if resolver is None:
        if node_id in ENGINE_GATE_STUBS:
            return {
                "ok": False,
                "code": "ENGINE_GATE_STUB",
                "message": (
                    f"Engine gate {node_id!r} has no resolver yet (workflow-02 stub; "
                    "see ENGINE_GATE_STUBS in gates.py)"
                ),
            }
        return {"ok": False, "code": "ENGINE_GATE_UNKNOWN", "message": f"No engine resolver for {node_id!r}"}

    produces = node.get("produces") or {}
    options = {str(item) for item in (produces.get("options") or [])}
    outcome = resolver(snapshot, run_dir=run_dir)
    if not outcome.get("ok"):
        return outcome

    decision = str(outcome.get("decision", ""))
    if decision not in options:
        return {
            "ok": False,
            "code": "INVALID_ENGINE_DECISION",
            "message": f"Resolver produced {decision!r}, not in gate options {sorted(options)}",
        }
    return outcome


def resolve_engine_gate(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
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

    if visit.get("decision") is not None:
        return {"ok": False, "code": "GATE_ALREADY_RESOLVED", "message": "Gate visit already has a decision"}

    decision_outcome = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    if not decision_outcome.get("ok"):
        return decision_outcome

    decision = str(decision_outcome["decision"])
    visit_id = str(visit["id"])
    node_id = str(visit["node_id"])

    visit["decision"] = decision
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="gate.decided",
        visit_id=visit_id,
        node_id=node_id,
        payload={
            "decision": decision,
            "decider": "engine",
            "rule_id": decision_outcome.get("rule_id"),
            "evidence_refs": decision_outcome.get("evidence_refs") or [],
        },
    )
    append_event(
        snapshot,
        event_type="gate.resolved",
        visit_id=visit_id,
        node_id=node_id,
        payload={"decision": decision, "decider": "engine"},
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
