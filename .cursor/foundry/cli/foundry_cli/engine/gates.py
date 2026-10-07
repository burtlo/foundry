"""Gate decision handling and engine gate resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.engine.evidence import (
    AGENT_RECEIPT_SCHEMA,
    agent_receipt_summary,
    intake_receipt_summary,
    load_linked_artifact,
    load_linked_receipt,
    sealed_step_visit_id,
)
from foundry_cli.engine.gate_rules import (
    evaluate_gate_rules,
    examine_check_ids,
    examine_fail_codes,
    load_gate_rules,
)
from foundry_cli.engine.lifecycle import _seal_visit_and_route, update_active_visit
from foundry_cli.engine.loop_limits import (
    evaluate_limit_flow_check,
    repair_loop_summary_for_snapshot,
    reverify_loop_summary_for_snapshot,
)
from foundry_cli.ledger import append_event, ledger_events
from foundry_cli.paths import resolve_run_uri
from foundry_cli.registry import get_node

__all__ = [
    "ENGINE_GATE_STUBS",
    "decide_gate",
    "gate_examine_check_ids",
    "repair_loop_summary_for_snapshot",
    "resolve_engine_gate",
    "resolve_engine_gate_decision",
    "reverify_loop_summary_for_snapshot",
]

# Engine gates without a gate.rules.yaml remain stubs until their workflow slice lands.
ENGINE_GATE_STUBS: frozenset[str] = frozenset()


def gate_examine_check_ids(
    gate_node_id: str, foundry_bundle: Path | None = None
) -> tuple[str, ...]:
    """Authored on_examine check ids for an engine gate, read from its node.yaml."""
    return examine_check_ids(gate_node_id, foundry_bundle)


def _latest_check_recorded(
    snapshot: dict[str, Any],
    *,
    visit_id: str,
    check_id: str,
    hook: str = "on_examine",
) -> str | None:
    recorded: str | None = None
    for event in ledger_events(snapshot):
        if not isinstance(event, dict) or event.get("type") != "check.recorded":
            continue
        if event.get("visit_id") != visit_id:
            continue
        payload = event.get("payload") or {}
        if payload.get("hook") != hook or payload.get("check_id") != check_id:
            continue
        result = payload.get("result")
        if result is not None:
            recorded = str(result)
    return recorded


def _require_gate_examine_checks(
    snapshot: dict[str, Any],
    *,
    gate_visit_id: str,
    check_ids: tuple[str, ...],
    fail_codes: dict[str, str],
) -> dict[str, Any] | None:
    """Fail closed when on_examine checks are missing or not pass (REL-014 thin resolvers)."""
    for check_id in check_ids:
        recorded = _latest_check_recorded(snapshot, visit_id=gate_visit_id, check_id=check_id)
        if recorded is None:
            live_pass = evaluate_limit_flow_check(snapshot, check_id)
            if live_pass is not None:
                if live_pass:
                    continue
                limit_code = fail_codes.get(check_id)
                if limit_code:
                    return {
                        "ok": False,
                        "code": limit_code,
                        "message": f"Live limit check {check_id!r} failed",
                    }
            return {
                "ok": False,
                "code": "EVIDENCE_MISSING",
                "message": f"Sealed examine check {check_id!r} not recorded for gate visit",
            }
        if recorded != "pass":
            limit_code = fail_codes.get(check_id)
            if limit_code:
                return {
                    "ok": False,
                    "code": limit_code,
                    "message": f"Examine check {check_id!r} result is {recorded!r}",
                }
            return {
                "ok": False,
                "code": "EVIDENCE_MISSING",
                "message": f"Examine check {check_id!r} did not pass",
            }
    return None


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


def intake_receipt_summary_for_sealed_step(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
    step_node_id: str,
) -> dict[str, Any] | None:
    """Public read model for steward context (execute/verify intake gates)."""
    return intake_receipt_summary(snapshot, run_dir=run_dir, step_node_id=step_node_id)


def test_receipt_summary_for_sealed_step(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
    step_node_id: str = "execute.test",
) -> dict[str, Any] | None:
    """Public read model for steward context (execute.test.gate)."""
    return agent_receipt_summary(snapshot, run_dir=run_dir, step_node_id=step_node_id)


def commit_receipt_summary_for_sealed_step(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
    step_node_id: str = "execute.commit",
) -> dict[str, Any] | None:
    """Public read model for steward context (execute.commit.gate)."""
    return test_receipt_summary_for_sealed_step(
        snapshot, run_dir=run_dir, step_node_id=step_node_id
    )


def code_quality_receipt_summary_for_sealed_step(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
    step_node_id: str = "verify.code_quality",
) -> dict[str, Any] | None:
    """Public read model for steward context (verify.code_quality.gate)."""
    return test_receipt_summary_for_sealed_step(
        snapshot, run_dir=run_dir, step_node_id=step_node_id
    )


def verify_acceptance_evidence_for_sealed_step(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
    step_node_id: str = "verify.acceptance",
) -> dict[str, Any] | None:
    """Public read model for steward context (verify.acceptance.gate)."""
    acceptance_visit_id = sealed_step_visit_id(snapshot, step_node_id)
    if not acceptance_visit_id:
        return None

    findings = load_linked_artifact(snapshot, acceptance_visit_id, "verify-findings", run_dir)
    findings_summary: dict[str, Any] = {
        "visit_id": acceptance_visit_id,
        "gate_decision": None,
        "evidence_ok": None,
        "verdict": None,
        "missing_file": None,
    }
    if findings is None:
        pass
    elif findings.get("_missing_file"):
        findings_summary["missing_file"] = findings["_missing_file"]
    else:
        gate_decision = findings.get("gate_decision")
        findings_summary["gate_decision"] = (
            str(gate_decision).strip().lower() if gate_decision is not None else None
        )
        findings_summary["evidence_ok"] = findings.get("evidence_ok")
        verdict = findings.get("verdict")
        findings_summary["verdict"] = str(verdict) if verdict is not None else None

    receipt = load_linked_receipt(snapshot, acceptance_visit_id, AGENT_RECEIPT_SCHEMA, run_dir)
    receipt_summary: dict[str, Any] = {
        "visit_id": acceptance_visit_id,
        "status": None,
        "receipt_id": None,
        "resolved_path": None,
    }
    if receipt is None:
        pass
    elif receipt.get("_missing_file"):
        receipt_summary["missing_file"] = receipt["_missing_file"]
    else:
        receipt_id = receipt.get("receipt_id")
        path_uri = None
        for event in reversed(ledger_events(snapshot)):
            if not isinstance(event, dict) or event.get("type") != "receipt.linked":
                continue
            if event.get("visit_id") != acceptance_visit_id:
                continue
            payload = event.get("payload") or {}
            if payload.get("schema") != AGENT_RECEIPT_SCHEMA:
                continue
            path_uri = payload.get("path")
            break
        resolved_path = None
        if isinstance(path_uri, str):
            resolved_path = str(resolve_run_uri(path_uri, run_dir, acceptance_visit_id))
        receipt_summary["status"] = str(receipt.get("status") or "")
        receipt_summary["receipt_id"] = str(receipt_id) if receipt_id else None
        receipt_summary["resolved_path"] = resolved_path

    return {
        "visit_id": acceptance_visit_id,
        "verify_findings": findings_summary,
        "acceptance_receipt": receipt_summary,
    }


def resolve_engine_gate_decision(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    run_dir: Path,
    foundry_bundle: Path | None = None,
) -> dict[str, Any]:
    node_id = str(visit["node_id"])
    node = get_node(flow, node_id)
    if str(node.get("decider")) != "engine":
        return {"ok": False, "code": "NOT_ENGINE_GATE", "message": f"{node_id} is not an engine gate"}

    rules = load_gate_rules(node_id, foundry_bundle)
    if rules is None:
        if node_id in ENGINE_GATE_STUBS:
            return {
                "ok": False,
                "code": "ENGINE_GATE_STUB",
                "message": (
                    f"Engine gate {node_id!r} has no gate.rules.yaml yet (workflow-02 stub; "
                    "see ENGINE_GATE_STUBS in gates.py)"
                ),
            }
        return {"ok": False, "code": "ENGINE_GATE_UNKNOWN", "message": f"No gate rules for {node_id!r}"}

    check_err = _require_gate_examine_checks(
        snapshot,
        gate_visit_id=str(visit["id"]),
        check_ids=examine_check_ids(node_id, foundry_bundle),
        fail_codes=examine_fail_codes(rules),
    )
    if check_err is not None:
        return check_err

    produces = node.get("produces") or {}
    options = {str(item) for item in (produces.get("options") or [])}
    outcome = evaluate_gate_rules(snapshot, visit, rules, run_dir=run_dir)
    if not outcome.get("ok"):
        return outcome

    decision = str(outcome.get("decision", ""))
    if decision not in options:
        return {
            "ok": False,
            "code": "INVALID_ENGINE_DECISION",
            "message": f"Gate rules produced {decision!r}, not in gate options {sorted(options)}",
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

    decision_outcome = resolve_engine_gate_decision(
        snapshot, visit, flow, run_dir=run_dir, foundry_bundle=foundry_bundle
    )
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
