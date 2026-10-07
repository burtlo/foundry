"""Bounded run advancement until wait, halt, completion, or step budget."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.constants import KIND_GATE, LIFECYCLE_OPENED, LIFECYCLE_SEALED
from foundry_cli.engine.advance_classifier import _work_prompt_from_snapshot
from foundry_cli.engine.agent.dispatch import (
    ensure_agent_request,
    visit_has_accepted_task,
    visit_has_accepted_task_result,
)
from foundry_cli.engine.agent.tasks import (
    EXECUTE_PLAN_TASK_ID,
    SHAPE_EXAMINE_TASK_ID,
    SHAPE_PRESENT_TASK_ID,
    SHAPE_RECORD_TASK_ID,
    VERIFY_ACCEPTANCE_TASK_ID,
    task_registry_binding_exists,
)
from foundry_cli.engine.blocked_intake import (
    apply_blocked_intake_wait,
    host_boundary_wait_blocked_intake,
)
from foundry_cli.engine.execute_step_executor import run_execute_plan_complete
from foundry_cli.engine.examination_state import derive_open_clarifying_questions_count
from foundry_cli.engine.gates import resolve_engine_gate
from foundry_cli.engine.lifecycle import active_visit
from foundry_cli.engine.mechanism_runner import MechanismRunner
from foundry_cli.engine.node_capability import (
    should_emit_unsupported_operator_wait,
    unsupported_request_ref,
    unsupported_wait_summary,
)
from foundry_cli.engine.node_runtime_profile import AdvanceMode, load_node_runtime_profile
from foundry_cli.engine.run_status_reason import clear_status_reason
from foundry_cli.engine.shape_step_executor import (
    run_shape_examine_complete,
    run_shape_present_complete,
    run_shape_record_complete,
)
from foundry_cli.engine.verify_step_executor import run_verify_acceptance_complete
from foundry_cli.engine.wait_state import clear_run_wait, set_run_wait
from foundry_cli.ledger import ledger_events
from foundry_cli.registry import get_node

DEFAULT_STEP_BUDGET = 8

TERMINAL_RUN_STATUSES = frozenset(
    {
        "completed",
        "halted",
        "execution_error",
        "definition_error",
    }
)

_TASK_BOUND_COMPLETE: dict[str, dict[str, Any]] = {
    SHAPE_EXAMINE_TASK_ID: {
        "run_complete": run_shape_examine_complete,
        "complete_reason": "examine_complete",
        "wait_summary": "Shape examination judgment required",
    },
    SHAPE_PRESENT_TASK_ID: {
        "run_complete": run_shape_present_complete,
        "complete_reason": "present_complete",
        "wait_summary": "Shape presentation judgment required",
    },
    SHAPE_RECORD_TASK_ID: {
        "run_complete": run_shape_record_complete,
        "complete_reason": "record_complete",
        "wait_summary": "Shape record judgment required",
    },
    EXECUTE_PLAN_TASK_ID: {
        "run_complete": run_execute_plan_complete,
        "complete_reason": "execute_plan_complete",
        "wait_summary": "Execute plan judgment required",
    },
    VERIFY_ACCEPTANCE_TASK_ID: {
        "run_complete": run_verify_acceptance_complete,
        "complete_reason": "verify_acceptance_complete",
        "wait_summary": "Verify acceptance judgment required",
    },
}

def _work_prompt_is_present(snapshot: dict[str, Any]) -> bool:
    prompt = _work_prompt_from_snapshot(snapshot)
    return isinstance(prompt, str) and bool(prompt.strip())


def _execution_error_outcome(result: dict[str, Any]) -> dict[str, Any]:
    return {"progressed": True, "reason": "execution_error", "error": result}


def _complete_outcome(reason: str, result: dict[str, Any]) -> dict[str, Any]:
    return {"progressed": True, "reason": reason, "detail": result}


def _task_accept_predicate(
    snapshot: dict[str, Any],
    *,
    visit_id: str,
    task_id: str,
    foundry_bundle: Path | None,
) -> bool:
    if foundry_bundle is None:
        return visit_has_accepted_task_result(snapshot, visit_id=visit_id, task_id=task_id)
    return visit_has_accepted_task(
        snapshot,
        visit_id=visit_id,
        task_id=task_id,
        foundry_bundle=foundry_bundle,
    )


def _task_wait_summary(task_id: str) -> str:
    details = _TASK_BOUND_COMPLETE.get(task_id)
    if details is None:
        return f"Task judgment required ({task_id})"
    return str(details["wait_summary"])


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

    profile = None
    if foundry_bundle is not None:
        profile = load_node_runtime_profile(node_id, flow, foundry_bundle)

    if profile is not None and profile.advance_mode == AdvanceMode.TASK:
        task_id = profile.task_id or node_id
        if _task_accept_predicate(
            snapshot,
            visit_id=visit_id,
            task_id=task_id,
            foundry_bundle=foundry_bundle,
        ):
            if task_id == SHAPE_EXAMINE_TASK_ID:
                state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
                open_count = derive_open_clarifying_questions_count(state)
                if open_count > 0:
                    return set_run_wait(
                        snapshot,
                        kind="user_input",
                        visit_id=visit_id,
                        summary=f"{open_count} clarifying question(s) need answers",
                        request_ref=f"questions:{visit_id}",
                    )
            return None
        request_ref = f"task:{node_id}"
        if workspace is not None and foundry_bundle is not None and run_dir is not None:
            request_ref = ensure_agent_request(
                snapshot,
                visit,
                flow,
                task_id=task_id,
                foundry_bundle=foundry_bundle,
                workspace=workspace,
                run_dir=run_dir,
            )
        return set_run_wait(
            snapshot,
            kind="agent",
            visit_id=visit_id,
            summary=_task_wait_summary(task_id),
            request_ref=request_ref,
        )

    if profile is not None and profile.advance_mode == AdvanceMode.HOST:
        blocked_wait = host_boundary_wait_blocked_intake(
            snapshot,
            visit,
            flow=flow,
            foundry_bundle=foundry_bundle,
            workspace=workspace,
            run_dir=run_dir,
        )
        if blocked_wait is not None:
            return blocked_wait
        if node_id == "shape.intake" and not _work_prompt_is_present(snapshot):
            return set_run_wait(
                snapshot,
                kind="operator",
                visit_id=visit_id,
                summary="Shape intake requires work_prompt in run config or state",
                request_ref="intake:work_prompt",
            )
        if profile.host_only_boundary:
            return None
        return None

    if profile is not None and profile.advance_mode == AdvanceMode.GIT_MECHANICAL:
        return None

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
    if foundry_bundle is not None and profile is not None and profile.host_only_boundary:
        return None
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


def _task_bound_advance(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    task_id: str,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any] | None:
    if str(visit.get("lifecycle")) != LIFECYCLE_OPENED:
        return None
    complete = _TASK_BOUND_COMPLETE.get(task_id)
    if complete is None:
        return None
    visit_id = str(visit.get("id", ""))
    if not _task_accept_predicate(
        snapshot,
        visit_id=visit_id,
        task_id=task_id,
        foundry_bundle=foundry_bundle,
    ):
        return None

    run_complete = complete["run_complete"]
    result = run_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not result.get("ok"):
        snapshot["status"] = "execution_error"
        return _execution_error_outcome(result)
    clear_run_wait(snapshot)
    return _complete_outcome(str(complete["complete_reason"]), result)


def _extract_mechanism_complete_result(mechanism_result: dict[str, Any]) -> dict[str, Any]:
    fallback: dict[str, Any] | None = None
    for step in mechanism_result.get("steps", []):
        if not isinstance(step, dict):
            continue
        result = step.get("result")
        if not isinstance(result, dict):
            continue
        fallback = result
        if "intake_status" in result or "transitioned" in result or "reopened" in result:
            return result
    return fallback if isinstance(fallback, dict) else mechanism_result


def _mechanism_advance(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    operations_ref: str,
) -> dict[str, Any] | None:
    node_id = str(visit.get("node_id", ""))
    lifecycle = str(visit.get("lifecycle"))
    if lifecycle not in (LIFECYCLE_OPENED, "examined"):
        return None

    mechanism_result = MechanismRunner().run(
        snapshot,
        visit,
        flow,
        operations_ref=operations_ref,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not mechanism_result.get("ok"):
        failed_result = mechanism_result.get("result")
        if isinstance(failed_result, dict) and bool(failed_result.get("reopened")):
            reopened_reason = f"{node_id.replace('.', '_')}_reopened"
            return {"progressed": True, "reason": reopened_reason, "detail": failed_result}
        snapshot["status"] = "execution_error"
        return _execution_error_outcome(
            failed_result if isinstance(failed_result, dict) else mechanism_result
        )

    if str(mechanism_result.get("status")) == "wait":
        wait = mechanism_result.get("wait")
        if isinstance(wait, dict) and str(wait.get("kind") or "") == "boundary":
            reason = str(wait.get("request_ref") or wait.get("reason") or "boundary")
            return {"progressed": False, "reason": reason}
        return {"progressed": False, "reason": "wait", "wait": wait}

    complete_result = _extract_mechanism_complete_result(mechanism_result)
    if (
        complete_result.get("transitioned") is False
        and complete_result.get("intake_status") == "blocked"
    ):
        apply_blocked_intake_wait(snapshot, visit, complete_result)
        return {"progressed": True, "reason": "intake_blocked", "detail": complete_result}

    clear_status_reason(snapshot)
    clear_run_wait(snapshot)
    reason = f"{node_id.replace('.', '_')}_complete"
    if node_id == "shape.intake":
        reason = "intake_complete"
    if reason == "deliver_stub_complete" and str(snapshot.get("status")) != "completed":
        snapshot["status"] = "completed"
    return _complete_outcome(reason, complete_result)


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
    if str(visit.get("kind")) == KIND_GATE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        gate_node = get_node(flow, node_id)
        if str(gate_node.get("decider")) == "engine" and visit.get("decision") is None:
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
                return {"progressed": True, "reason": "engine_gate_failed", "error": result}
            clear_run_wait(snapshot)
            return {"progressed": True, "reason": "engine_gate_resolved", "detail": result}

    profile = load_node_runtime_profile(node_id, flow, foundry_bundle)
    if profile.advance_mode == AdvanceMode.TASK:
        outcome = _task_bound_advance(
            snapshot,
            visit,
            flow,
            task_id=profile.task_id or node_id,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if outcome is not None:
            return outcome
        return {"progressed": False, "reason": "task_pending"}

    if profile.advance_mode in (AdvanceMode.HOST, AdvanceMode.GIT_MECHANICAL):
        if not profile.operations_ref:
            snapshot["status"] = "execution_error"
            return _execution_error_outcome(
                {
                    "ok": False,
                    "code": "OPERATIONS_NOT_BOUND",
                    "message": f"{node_id} requires node operations binding",
                }
            )
        outcome = _mechanism_advance(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
            operations_ref=profile.operations_ref,
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
