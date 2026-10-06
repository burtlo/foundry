"""Gate decision handling and engine gate resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from foundry_cli.engine.hooks import (
    AGENT_RECEIPT_SCHEMA,
    _load_agent_receipt_for_visit,
    _latest_sealed_visit_id,
)
from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
from foundry_cli.engine.lifecycle import _seal_visit_and_route, update_active_visit
from foundry_cli.engine.routing import _config_limit
from foundry_cli.ledger import append_event, count_events, ledger_events
from foundry_cli.paths import resolve_run_uri
from foundry_cli.registry import get_node

# Engine gates without a resolver remain stubs until their workflow slice lands.
ENGINE_GATE_STUBS: frozenset[str] = frozenset()


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
    intake_visit_id = _latest_sealed_visit_id(snapshot, step_node_id)
    if not intake_visit_id:
        return None
    receipt = _load_intake_receipt_for_visit(snapshot, intake_visit_id, run_dir)
    if receipt is None:
        return {"visit_id": intake_visit_id, "status": None, "receipt_id": None, "resolved_path": None}
    if receipt.get("_missing_file"):
        return {
            "visit_id": intake_visit_id,
            "status": None,
            "receipt_id": None,
            "resolved_path": None,
            "missing_file": receipt["_missing_file"],
        }
    receipt_id = receipt.get("receipt_id")
    path_uri = None
    for event in reversed(ledger_events(snapshot)):
        if not isinstance(event, dict) or event.get("type") != "receipt.linked":
            continue
        if event.get("visit_id") != intake_visit_id:
            continue
        payload = event.get("payload") or {}
        if payload.get("schema") != INTAKE_RECEIPT_SCHEMA:
            continue
        path_uri = payload.get("path")
        break
    resolved_path = None
    if isinstance(path_uri, str):
        resolved_path = str(resolve_run_uri(path_uri, run_dir, intake_visit_id))
    return {
        "visit_id": intake_visit_id,
        "status": str(receipt.get("status") or ""),
        "receipt_id": str(receipt_id) if receipt_id else None,
        "resolved_path": resolved_path,
    }


def test_receipt_summary_for_sealed_step(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
    step_node_id: str = "execute.test",
) -> dict[str, Any] | None:
    """Public read model for steward context (execute.test.gate)."""
    test_visit_id = _latest_sealed_visit_id(snapshot, step_node_id)
    if not test_visit_id:
        return None
    receipt = _load_agent_receipt_for_visit(snapshot, test_visit_id, run_dir)
    if receipt is None:
        return {"visit_id": test_visit_id, "status": None, "receipt_id": None, "resolved_path": None, "commands": []}
    if receipt.get("_missing_file"):
        return {
            "visit_id": test_visit_id,
            "status": None,
            "receipt_id": None,
            "resolved_path": None,
            "missing_file": receipt["_missing_file"],
            "commands": [],
        }
    receipt_id = receipt.get("receipt_id")
    path_uri = None
    for event in reversed(ledger_events(snapshot)):
        if not isinstance(event, dict) or event.get("type") != "receipt.linked":
            continue
        if event.get("visit_id") != test_visit_id:
            continue
        payload = event.get("payload") or {}
        if payload.get("schema") != AGENT_RECEIPT_SCHEMA:
            continue
        path_uri = payload.get("path")
        break
    resolved_path = None
    if isinstance(path_uri, str):
        resolved_path = str(resolve_run_uri(path_uri, run_dir, test_visit_id))
    raw_commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    commands: list[dict[str, Any]] = []
    for item in raw_commands:
        if not isinstance(item, dict):
            continue
        commands.append(
            {
                "command": str(item.get("command") or ""),
                "exit_code": int(item.get("exit_code", 1)),
            }
        )
    return {
        "visit_id": test_visit_id,
        "status": str(receipt.get("status") or ""),
        "receipt_id": str(receipt_id) if receipt_id else None,
        "resolved_path": resolved_path,
        "commands": commands,
    }


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


def repair_loop_summary_for_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Ledger repair-loop count vs config.limits.repair for steward context."""
    repair_count = count_events(snapshot, "connection.taken", loop="repair")
    limit = _config_limit(snapshot, "repair", 2)
    return {
        "repair_count": repair_count,
        "limit": limit,
        "within_limit": repair_count <= limit,
    }


def _execute_repair_limit_gate_decision(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    """Allow proceed when repair loop count is within config.limits.repair."""
    summary = repair_loop_summary_for_snapshot(snapshot)
    repair_count = summary["repair_count"]
    limit = summary["limit"]
    if not summary["within_limit"]:
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


def _execute_commit_gate_decision(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    state = snapshot.get("state")
    if not isinstance(state, dict) or not state.get("final_commit_sha"):
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": "final_commit_sha not recorded for execute.commit",
        }
    commit_visit_id = _latest_sealed_visit_id(snapshot, "execute.commit")
    if not commit_visit_id:
        return {"ok": False, "code": "EVIDENCE_MISSING", "message": "execute.commit visit is not sealed"}
    receipt = _load_agent_receipt_for_visit(snapshot, commit_visit_id, run_dir)
    evidence_refs: list[str] = []
    if receipt and receipt.get("receipt_id"):
        evidence_refs = [str(receipt["receipt_id"])]
    return {
        "ok": True,
        "decision": "pass",
        "rule_id": "execute.commit.gate/final-commit-recorded",
        "evidence_refs": evidence_refs,
    }


def _verify_intake_gate_decision(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    intake_visit_id = _latest_sealed_visit_id(snapshot, "verify.intake")
    if not intake_visit_id:
        return {"ok": False, "code": "EVIDENCE_MISSING", "message": "verify.intake visit is not sealed"}

    receipt = _load_intake_receipt_for_visit(snapshot, intake_visit_id, run_dir)
    if receipt is None:
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": "No intake receipt linked for sealed verify.intake visit",
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
            "rule_id": "verify.intake.gate/intake-passed",
            "evidence_refs": evidence_refs,
        }
    return {
        "ok": False,
        "code": "EVIDENCE_MISSING",
        "message": f"Verify intake receipt status is {status!r}; gate cannot pass",
        "evidence_refs": evidence_refs,
    }


def verify_acceptance_evidence_for_sealed_step(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
    step_node_id: str = "verify.acceptance",
) -> dict[str, Any] | None:
    """Public read model for steward context (verify.acceptance.gate)."""
    acceptance_visit_id = _latest_sealed_visit_id(snapshot, step_node_id)
    if not acceptance_visit_id:
        return None

    findings = _load_verify_findings_for_visit(snapshot, acceptance_visit_id, run_dir)
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

    receipt = _load_agent_receipt_for_visit(snapshot, acceptance_visit_id, run_dir)
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


def _load_verify_findings_for_visit(
    snapshot: dict[str, Any],
    visit_id: str,
    run_dir: Path,
) -> dict[str, Any] | None:
    for event in reversed(ledger_events(snapshot)):
        if not isinstance(event, dict) or event.get("type") != "artifact.linked":
            continue
        if event.get("visit_id") != visit_id:
            continue
        payload = event.get("payload") or {}
        if payload.get("artifact_id") != "verify-findings":
            continue
        path_uri = payload.get("uri")
        if not isinstance(path_uri, str):
            return None
        artifact_path = resolve_run_uri(path_uri, run_dir, visit_id)
        if not artifact_path.is_file():
            return {"_missing_file": str(artifact_path)}
        return json.loads(artifact_path.read_text(encoding="utf-8"))
    return None


def _verify_acceptance_gate_decision(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    acceptance_visit_id = _latest_sealed_visit_id(snapshot, "verify.acceptance")
    if not acceptance_visit_id:
        return {"ok": False, "code": "EVIDENCE_MISSING", "message": "verify.acceptance visit is not sealed"}

    findings = _load_verify_findings_for_visit(snapshot, acceptance_visit_id, run_dir)
    if findings is None:
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": "verify-findings artifact missing for sealed verify.acceptance",
        }
    if findings.get("_missing_file"):
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": f"verify-findings file missing: {findings['_missing_file']}",
        }

    decision_raw = findings.get("gate_decision")
    if decision_raw is None or not str(decision_raw).strip():
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": "verify-findings gate_decision missing",
        }
    decision = str(decision_raw).strip().lower()
    allowed = {"pass", "replan", "reshape", "rework_execute"}
    if decision not in allowed:
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": f"verify-findings gate_decision {decision!r} is not routable",
        }
    if decision == "pass" and findings.get("evidence_ok") is not True:
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": "verify-findings evidence_ok must be true to pass acceptance gate",
        }
    return {
        "ok": True,
        "decision": decision,
        "rule_id": f"verify.acceptance.gate/findings-{decision}",
        "evidence_refs": [],
    }


def _verify_code_quality_gate_decision(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    quality_visit_id = _latest_sealed_visit_id(snapshot, "verify.code_quality")
    if not quality_visit_id:
        return {"ok": False, "code": "EVIDENCE_MISSING", "message": "verify.code_quality visit is not sealed"}

    sealed = None
    for event in reversed(ledger_events(snapshot)):
        if event.get("type") == "visit.sealed" and event.get("visit_id") == quality_visit_id:
            sealed = event
            break
    if sealed is not None:
        outcome = (sealed.get("payload") or {}).get("outcome")
        if outcome == "not_applicable":
            return {
                "ok": True,
                "decision": "pass",
                "rule_id": "verify.code_quality.gate/skipped",
                "evidence_refs": [],
            }

    receipt = _load_agent_receipt_for_visit(snapshot, quality_visit_id, run_dir)
    if receipt is None:
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": "No agent receipt for verify.code_quality",
        }
    if receipt.get("_missing_file"):
        return {
            "ok": False,
            "code": "EVIDENCE_MISSING",
            "message": f"Agent receipt missing: {receipt['_missing_file']}",
        }

    receipt_id = receipt.get("receipt_id")
    evidence_refs = [str(receipt_id)] if receipt_id else []
    commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    if commands and any(isinstance(c, dict) and c.get("exit_code", 0) != 0 for c in commands):
        return {
            "ok": True,
            "decision": "repair",
            "rule_id": "verify.code_quality.gate/command-failed",
            "evidence_refs": evidence_refs,
        }
    if str(receipt.get("status")) in ("failed", "partial"):
        return {
            "ok": True,
            "decision": "repair",
            "rule_id": "verify.code_quality.gate/receipt-failed",
            "evidence_refs": evidence_refs,
        }
    return {
        "ok": True,
        "decision": "pass",
        "rule_id": "verify.code_quality.gate/receipt-pass",
        "evidence_refs": evidence_refs,
    }


_ENGINE_RESOLVERS: dict[str, Callable[..., dict[str, Any]]] = {
    "execute.intake.gate": _execute_intake_gate_decision,
    "execute.test.gate": _execute_test_gate_decision,
    "execute.repair.limit.gate": _execute_repair_limit_gate_decision,
    "execute.commit.gate": _execute_commit_gate_decision,
    "verify.intake.gate": _verify_intake_gate_decision,
    "verify.acceptance.gate": _verify_acceptance_gate_decision,
    "verify.code_quality.gate": _verify_code_quality_gate_decision,
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
