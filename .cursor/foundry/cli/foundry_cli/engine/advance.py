"""Bounded run advancement until wait, halt, completion, or step budget."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.constants import KIND_GATE, LIFECYCLE_OPENED, LIFECYCLE_SEALED
from foundry_cli.engine.agent.tasks import task_registry_binding_exists
from foundry_cli.engine.advance_classifier import (
    AdvanceNodeClass,
    classify_advance_node,
    dispatch_git_mechanical_advance,
    dispatch_git_mechanical_boundary_wait,
    dispatch_host_step_advance,
    dispatch_host_step_boundary_wait,
    dispatch_task_bound_advance,
    dispatch_task_bound_boundary_wait,
)
from foundry_cli.engine.execute_step_executor import EXECUTE_BUILD_NODE
from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
from foundry_cli.engine.gates import resolve_engine_gate
from foundry_cli.engine.lifecycle import active_visit
from foundry_cli.engine.node_capability import (
    should_emit_unsupported_operator_wait,
    unsupported_request_ref,
    unsupported_wait_summary,
)
from foundry_cli.ledger import count_events, ledger_events
from foundry_cli.registry import get_node
from foundry_cli.engine.wait_state import clear_run_wait, set_run_wait

DEFAULT_STEP_BUDGET = 8

TERMINAL_RUN_STATUSES = frozenset(
    {
        "completed",
        "halted",
        "execution_error",
        "definition_error",
    }
)


EXECUTE_BUILD_PARKED_VISIT_STATE_KEY = "execute_build_parked_visit_id"
EXECUTE_PLAN_TO_BUILD_CONNECTION = "execute.plan-to-execute.build"


def _visit_admission_source(snapshot: dict[str, Any], visit_id: str) -> str | None:
    for event in ledger_events(snapshot):
        if not isinstance(event, dict) or event.get("type") != "visit.admitted":
            continue
        if str(event.get("visit_id")) != visit_id:
            continue
        payload = event.get("payload") or {}
        source = payload.get("source")
        if isinstance(source, str) and source.strip():
            return source.strip()
        return None
    return None


def _connection_taken_payload(snapshot: dict[str, Any], connection_id: str) -> dict[str, Any] | None:
    for event in reversed(ledger_events(snapshot)):
        if not isinstance(event, dict) or event.get("type") != "connection.taken":
            continue
        payload = event.get("payload") or {}
        if str(payload.get("connection_id")) == connection_id:
            return payload
    return None


def _visit_admitted_via_repair_loop(snapshot: dict[str, Any], visit_id: str) -> bool:
    """True when this visit was opened by a connection.taken with loop=repair."""
    source = _visit_admission_source(snapshot, visit_id)
    if not source:
        return False
    payload = _connection_taken_payload(snapshot, source)
    if not payload:
        return False
    loop = payload.get("loop")
    return isinstance(loop, str) and loop.strip() == "repair"


def _snapshot_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = snapshot.get("state")
    return state if isinstance(state, dict) else {}


def _execute_build_boundary_parked(snapshot: dict[str, Any], visit_id: str) -> bool:
    return str(_snapshot_state(snapshot).get(EXECUTE_BUILD_PARKED_VISIT_STATE_KEY) or "") == visit_id


def _park_execute_build_boundary(snapshot: dict[str, Any], visit_id: str) -> None:
    state = snapshot.setdefault("state", {})
    if isinstance(state, dict):
        state[EXECUTE_BUILD_PARKED_VISIT_STATE_KEY] = visit_id


def _clear_execute_build_park(snapshot: dict[str, Any]) -> None:
    state = snapshot.get("state")
    if isinstance(state, dict):
        state.pop(EXECUTE_BUILD_PARKED_VISIT_STATE_KEY, None)


def _should_park_at_execute_build_boundary(snapshot: dict[str, Any], visit_id: str) -> str | None:
    """Return advance stop reason when this opened visit should park before host build."""
    if _execute_build_boundary_parked(snapshot, visit_id):
        return None
    source = _visit_admission_source(snapshot, visit_id)
    if not source:
        return None
    if source == EXECUTE_PLAN_TO_BUILD_CONNECTION:
        return "execute_build_boundary"
    payload = _connection_taken_payload(snapshot, source)
    if payload and str(payload.get("loop") or "").strip() == "repair":
        return "repair_reentry_boundary"
    return None


def _intake_receipt_linked(snapshot: dict[str, Any], visit_id: str) -> bool:
    return (
        count_events(
            snapshot,
            "receipt.linked",
            visit_id=visit_id,
            schema=INTAKE_RECEIPT_SCHEMA,
        )
        > 0
    )


def _boundary_wait_for_visit(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path | None = None,
    foundry_bundle: Path | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Return a wait record when advancement must stop; None if engine work may continue."""
    if str(snapshot.get("status")) in TERMINAL_RUN_STATUSES:
        return None

    lifecycle = str(visit.get("lifecycle", ""))
    node_id = str(visit.get("node_id", ""))
    visit_id = str(visit.get("id", ""))
    kind = str(visit.get("kind", ""))

    if lifecycle == LIFECYCLE_SEALED:
        connection = None
        for event in reversed(ledger_events(snapshot)):
            if not isinstance(event, dict):
                continue
            if event.get("visit_id") != visit_id:
                continue
            if event.get("type") == "connection.taken":
                connection = event.get("payload")
                break
            if event.get("type") == "visit.sealed":
                break
        if connection is None:
            node = get_node(flow, node_id)
            node_kind = str(node.get("kind", kind))
            if node_kind != KIND_GATE and bool(node.get("terminal")):
                snapshot["status"] = "completed"
                clear_run_wait(snapshot)
        return None

    if lifecycle != LIFECYCLE_OPENED:
        return None

    if kind == KIND_GATE or str(get_node(flow, node_id).get("kind")) == KIND_GATE:
        gate_node = get_node(flow, node_id)
        if str(gate_node.get("decider")) == "engine":
            return None
        if visit.get("decision") is None:
            return set_run_wait(
                snapshot,
                kind="decision",
                visit_id=visit_id,
                summary=f"User gate {node_id} awaiting decision",
                request_ref=f"gate:{node_id}",
            )
        return None

    advance_class = classify_advance_node(
        node_id,
        flow,
        foundry_bundle=foundry_bundle,
    )
    if advance_class == AdvanceNodeClass.TASK_BOUND_STEP:
        return dispatch_task_bound_boundary_wait(
            node_id,
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )

    if advance_class == AdvanceNodeClass.GIT_MECHANICAL_STEP:
        return dispatch_git_mechanical_boundary_wait(
            node_id,
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )

    if advance_class == AdvanceNodeClass.HOST_STEP:
        return dispatch_host_step_boundary_wait(
            node_id,
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )

    if foundry_bundle is not None and should_emit_unsupported_operator_wait(
        node_id,
        flow,
        foundry_bundle=foundry_bundle,
    ):
        return set_run_wait(
            snapshot,
            kind="operator",
            visit_id=visit_id,
            summary=unsupported_wait_summary(node_id),
            request_ref=unsupported_request_ref(node_id),
        )

    flow_node = get_node(flow, node_id)
    if foundry_bundle is not None and task_registry_binding_exists(node_id, foundry_bundle):
        return set_run_wait(
            snapshot,
            kind="agent",
            visit_id=visit_id,
            summary=f"Agent task work required at {node_id}",
            request_ref=f"task:{node_id}",
        )
    if isinstance(flow_node.get("worker"), dict):
        return set_run_wait(
            snapshot,
            kind="agent",
            visit_id=visit_id,
            summary=f"Worker judgment required at {node_id}",
            request_ref=f"visit:{node_id}",
        )

    return set_run_wait(
        snapshot,
        kind="operator",
        visit_id=visit_id,
        summary=(
            f"Manual steps required at {node_id} "
            "(no agent task registry binding)"
        ),
        request_ref=f"operator:{node_id}",
    )


def _advance_once(
    snapshot: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any]:
    if str(snapshot.get("status")) in TERMINAL_RUN_STATUSES:
        return {"progressed": False, "reason": "terminal_status"}

    try:
        visit = active_visit(snapshot)
    except ValueError:
        snapshot["status"] = "completed"
        clear_run_wait(snapshot)
        return {"progressed": True, "reason": "no_active_visit"}

    wait = _boundary_wait_for_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if wait is not None:
        return {"progressed": False, "reason": "wait", "wait": wait}

    node_id = str(visit.get("node_id", ""))
    visit_id = str(visit.get("id", ""))
    if node_id == EXECUTE_BUILD_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        if _execute_build_boundary_parked(snapshot, visit_id):
            _clear_execute_build_park(snapshot)
        else:
            park_reason = _should_park_at_execute_build_boundary(snapshot, visit_id)
            if park_reason is not None:
                _park_execute_build_boundary(snapshot, visit_id)
                return {"progressed": False, "reason": park_reason}

    if str(visit.get("kind")) == KIND_GATE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        gate_node = get_node(flow, node_id)
        if str(gate_node.get("decider")) == "engine" and visit.get("decision") is None:
            if workspace is None or foundry_bundle is None or run_dir is None:
                return {"progressed": False, "reason": "engine_gate_missing_context"}
            result = resolve_engine_gate(
                snapshot,
                visit,
                flow,
                workspace=workspace,
                foundry_bundle=foundry_bundle,
                run_dir=run_dir,
            )
            if not result.get("ok"):
                from foundry_cli.engine.run_status_reason import set_status_reason

                error_code = str(result.get("code") or "")
                if error_code in (
                    "EVIDENCE_MISSING",
                    "EVIDENCE_CONFLICT",
                    "ENGINE_GATE_STUB",
                    "REPAIR_LIMIT_EXCEEDED",
                    "REVERIFY_LIMIT_EXCEEDED",
                ):
                    snapshot["status"] = "halted"
                    set_status_reason(
                        snapshot,
                        error_code,
                        message=str(result.get("message") or error_code),
                    )
                elif error_code == "DEFINITION_ERROR":
                    snapshot["status"] = "definition_error"
                else:
                    snapshot["status"] = "execution_error"
                return {
                    "progressed": True,
                    "reason": "engine_gate_failed",
                    "error": result,
                }
            clear_run_wait(snapshot)
            return {
                "progressed": True,
                "reason": "engine_gate_resolved",
                "detail": result,
            }

    advance_class = classify_advance_node(
        node_id,
        flow,
        foundry_bundle=foundry_bundle,
    )
    if advance_class == AdvanceNodeClass.TASK_BOUND_STEP:
        outcome = dispatch_task_bound_advance(
            node_id,
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if outcome is not None:
            return outcome

    if advance_class == AdvanceNodeClass.GIT_MECHANICAL_STEP:
        outcome = dispatch_git_mechanical_advance(
            node_id,
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if outcome is not None:
            return outcome

    if advance_class == AdvanceNodeClass.HOST_STEP:
        outcome = dispatch_host_step_advance(
            node_id,
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if outcome is not None:
            return outcome

    return {"progressed": False, "reason": "no_automatic_step"}


def _snapshot_fingerprint(snapshot: dict[str, Any]) -> tuple[Any, ...]:
    return (
        snapshot.get("wait"),
        snapshot.get("status"),
        snapshot.get("active_visit"),
        len(ledger_events(snapshot)),
    )


def advance_run(
    snapshot: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    step_budget: int = DEFAULT_STEP_BUDGET,
) -> dict[str, Any]:
    """Advance until wait, terminal status, error, or step budget."""
    fingerprint_before = _snapshot_fingerprint(snapshot)
    start_seq = len(ledger_events(snapshot))
    steps_taken = 0
    last_reason = "idle"

    while steps_taken < step_budget:
        prior_wait = snapshot.get("wait")
        outcome = _advance_once(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not outcome.get("progressed"):
            last_reason = str(outcome.get("reason", "idle"))
            if outcome.get("wait") is not None:
                last_reason = "wait"
            break
        steps_taken += 1
        last_reason = str(outcome.get("reason", "step"))
        if str(snapshot.get("status")) in TERMINAL_RUN_STATUSES:
            break
        if snapshot.get("wait") != prior_wait and snapshot.get("wait") is not None:
            break

    if snapshot.get("wait") is None:
        try:
            visit = active_visit(snapshot)
        except ValueError:
            visit = None
        if visit is not None:
            _boundary_wait_for_visit(
                snapshot,
                visit,
                flow,
                workspace=workspace,
                foundry_bundle=foundry_bundle,
                run_dir=run_dir,
            )

    mutated = _snapshot_fingerprint(snapshot) != fingerprint_before
    events_after = ledger_events(snapshot)[start_seq:]
    return {
        "ok": True,
        "steps_taken": steps_taken,
        "reason": last_reason,
        "status": str(snapshot.get("status")),
        "wait": snapshot.get("wait"),
        "active_visit": snapshot.get("active_visit"),
        "events_after": events_after,
        "mutated": mutated,
    }
