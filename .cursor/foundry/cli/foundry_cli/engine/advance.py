"""Bounded run advancement until wait, halt, completion, or step budget."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.constants import KIND_GATE, LIFECYCLE_OPENED, LIFECYCLE_SEALED
from foundry_cli.engine.agent.dispatch import (
    ensure_execute_plan_request,
    ensure_shape_examine_request,
    ensure_shape_present_request,
    ensure_shape_record_request,
    ensure_verify_acceptance_request,
    visit_has_accepted_proceed_plan,
    visit_has_accepted_proceed_presentation,
    visit_has_accepted_proceed_record,
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
from foundry_cli.engine.execute_step_executor import (
    EXECUTE_BRANCH_NODE,
    EXECUTE_BUILD_NODE,
    EXECUTE_COMMIT_NODE,
    EXECUTE_INTAKE_NODE,
    EXECUTE_PLAN_NODE,
    EXECUTE_TEST_NODE,
    run_execute_branch_complete,
    run_execute_build_complete,
    run_execute_commit_complete,
    run_execute_intake_complete,
    run_execute_plan_complete,
    run_execute_test_complete,
)
from foundry_cli.engine.verify_step_executor import (
    DELIVER_STUB_NODE,
    VERIFY_ACCEPTANCE_NODE,
    VERIFY_CODE_QUALITY_NODE,
    VERIFY_CODE_REVIEW_NODE,
    VERIFY_COMPLETE_NODE,
    VERIFY_INTAKE_NODE,
    run_deliver_stub_complete,
    run_verify_acceptance_complete,
    run_verify_code_quality_complete,
    run_verify_code_review_complete,
    run_verify_complete_complete,
    run_verify_intake_complete,
)
from foundry_cli.engine.shape_step_executor import (
    SHAPE_PRESENT_NODE,
    SHAPE_RECORD_NODE,
    run_shape_examine_complete,
    run_shape_present_complete,
    run_shape_record_complete,
)
from foundry_cli.engine.node_capability import _HOST_IMPLEMENTED_STEP_NODES
from foundry_cli.engine.examination_state import derive_open_clarifying_questions_count
from foundry_cli.engine.intake_executor import (
    INTAKE_RECEIPT_SCHEMA,
    run_shape_intake_complete,
)
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


def _work_prompt_from_snapshot(snapshot: dict[str, Any]) -> str | None:
    config = snapshot.get("config")
    if isinstance(config, dict):
        shape = config.get("shape")
        if isinstance(shape, dict):
            prompt = shape.get("work_prompt")
            if isinstance(prompt, str) and prompt.strip():
                return prompt
        direct = config.get("work_prompt")
        if isinstance(direct, str) and direct.strip():
            return direct
    state = snapshot.get("state")
    if isinstance(state, dict):
        prompt = state.get("work_prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt
    return None


def _work_prompt_is_present(snapshot: dict[str, Any]) -> bool:
    prompt = _work_prompt_from_snapshot(snapshot)
    return isinstance(prompt, str) and bool(prompt.strip())


def _source_from_snapshot(snapshot: dict[str, Any]) -> tuple[str, str | None]:
    config = snapshot.get("config")
    if isinstance(config, dict):
        shape = config.get("shape")
        if isinstance(shape, dict):
            source_type = str(shape.get("source_type") or "chat")
            source_ref = shape.get("source_ref")
            if source_ref is not None and not isinstance(source_ref, str):
                source_ref = None
            return source_type, source_ref
    return "chat", None


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

    if node_id == "shape.intake":
        if not _work_prompt_is_present(snapshot):
            return set_run_wait(
                snapshot,
                kind="operator",
                visit_id=visit_id,
                summary="Shape intake requires work_prompt in run config or state",
                request_ref="intake:work_prompt",
            )
        return None

    if node_id == SHAPE_EXAMINE_TASK_ID:
        if visit_has_accepted_task_result(
            snapshot,
            visit_id=visit_id,
            task_id=SHAPE_EXAMINE_TASK_ID,
        ):
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
            request_ref = ensure_shape_examine_request(
                snapshot,
                visit,
                flow,
                foundry_bundle=foundry_bundle,
                workspace=workspace,
                run_dir=run_dir,
            )
        return set_run_wait(
            snapshot,
            kind="agent",
            visit_id=visit_id,
            summary="Shape examination judgment required",
            request_ref=request_ref,
        )

    if node_id == SHAPE_PRESENT_TASK_ID:
        if visit_has_accepted_proceed_presentation(snapshot, visit_id=visit_id):
            return None
        request_ref = f"task:{node_id}"
        if workspace is not None and foundry_bundle is not None and run_dir is not None:
            request_ref = ensure_shape_present_request(
                snapshot,
                visit,
                flow,
                foundry_bundle=foundry_bundle,
                workspace=workspace,
                run_dir=run_dir,
            )
        return set_run_wait(
            snapshot,
            kind="agent",
            visit_id=visit_id,
            summary="Shape presentation judgment required",
            request_ref=request_ref,
        )

    if node_id == SHAPE_RECORD_TASK_ID:
        if visit_has_accepted_proceed_record(snapshot, visit_id=visit_id):
            return None
        request_ref = f"task:{node_id}"
        if workspace is not None and foundry_bundle is not None and run_dir is not None:
            request_ref = ensure_shape_record_request(
                snapshot,
                visit,
                flow,
                foundry_bundle=foundry_bundle,
                workspace=workspace,
                run_dir=run_dir,
            )
        return set_run_wait(
            snapshot,
            kind="agent",
            visit_id=visit_id,
            summary="Shape record judgment required",
            request_ref=request_ref,
        )

    if node_id == EXECUTE_PLAN_TASK_ID:
        if visit_has_accepted_proceed_plan(snapshot, visit_id=visit_id):
            return None
        request_ref = f"task:{node_id}"
        if workspace is not None and foundry_bundle is not None and run_dir is not None:
            request_ref = ensure_execute_plan_request(
                snapshot,
                visit,
                flow,
                foundry_bundle=foundry_bundle,
                workspace=workspace,
                run_dir=run_dir,
            )
        return set_run_wait(
            snapshot,
            kind="agent",
            visit_id=visit_id,
            summary="Execute plan judgment required",
            request_ref=request_ref,
        )

    if node_id == VERIFY_ACCEPTANCE_NODE:
        if visit_has_accepted_task_result(
            snapshot,
            visit_id=visit_id,
            task_id=VERIFY_ACCEPTANCE_TASK_ID,
        ):
            return None
        request_ref = f"task:{node_id}"
        if workspace is not None and foundry_bundle is not None and run_dir is not None:
            request_ref = ensure_verify_acceptance_request(
                snapshot,
                visit,
                flow,
                foundry_bundle=foundry_bundle,
                workspace=workspace,
                run_dir=run_dir,
            )
        return set_run_wait(
            snapshot,
            kind="agent",
            visit_id=visit_id,
            summary="Verify acceptance judgment required",
            request_ref=request_ref,
        )

    if node_id in _HOST_IMPLEMENTED_STEP_NODES:
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
                if result.get("code") in (
                    "EVIDENCE_MISSING",
                    "EVIDENCE_CONFLICT",
                    "ENGINE_GATE_STUB",
                    "REPAIR_LIMIT_EXCEEDED",
                ):
                    snapshot["status"] = "halted"
                elif result.get("code") == "DEFINITION_ERROR":
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

    if node_id == "shape.intake" and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        source_type, source_ref = _source_from_snapshot(snapshot)
        result = run_shape_intake_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
            work_prompt=_work_prompt_from_snapshot(snapshot),
            source_type=source_type,
            source_ref=source_ref,
        )
        if not result.get("ok"):
            snapshot["status"] = "execution_error"
            return {
                "progressed": True,
                "reason": "execution_error",
                "error": result,
            }
        clear_run_wait(snapshot)
        return {
            "progressed": True,
            "reason": "intake_complete",
            "detail": result,
        }

    if node_id == SHAPE_EXAMINE_TASK_ID and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        if visit_has_accepted_task_result(
            snapshot,
            visit_id=str(visit.get("id")),
            task_id=SHAPE_EXAMINE_TASK_ID,
        ):
            result = run_shape_examine_complete(
                snapshot,
                visit,
                flow,
                workspace=workspace,
                foundry_bundle=foundry_bundle,
                run_dir=run_dir,
            )
            if not result.get("ok"):
                snapshot["status"] = "execution_error"
                return {
                    "progressed": True,
                    "reason": "execution_error",
                    "error": result,
                }
            clear_run_wait(snapshot)
            return {
                "progressed": True,
                "reason": "examine_complete",
                "detail": result,
            }

    if node_id == SHAPE_PRESENT_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        if visit_has_accepted_proceed_presentation(
            snapshot,
            visit_id=str(visit.get("id")),
        ):
            result = run_shape_present_complete(
                snapshot,
                visit,
                flow,
                workspace=workspace,
                foundry_bundle=foundry_bundle,
                run_dir=run_dir,
            )
            if not result.get("ok"):
                snapshot["status"] = "execution_error"
                return {
                    "progressed": True,
                    "reason": "execution_error",
                    "error": result,
                }
            clear_run_wait(snapshot)
            return {
                "progressed": True,
                "reason": "present_complete",
                "detail": result,
            }

    if node_id == SHAPE_RECORD_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        if visit_has_accepted_proceed_record(
            snapshot,
            visit_id=str(visit.get("id")),
        ):
            result = run_shape_record_complete(
                snapshot,
                visit,
                flow,
                workspace=workspace,
                foundry_bundle=foundry_bundle,
                run_dir=run_dir,
            )
            if not result.get("ok"):
                snapshot["status"] = "execution_error"
                return {
                    "progressed": True,
                    "reason": "execution_error",
                    "error": result,
                }
            clear_run_wait(snapshot)
            return {
                "progressed": True,
                "reason": "record_complete",
                "detail": result,
            }

    if node_id == EXECUTE_INTAKE_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        result = run_execute_intake_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not result.get("ok"):
            snapshot["status"] = "execution_error"
            return {
                "progressed": True,
                "reason": "execution_error",
                "error": result,
            }
        clear_run_wait(snapshot)
        return {
            "progressed": True,
            "reason": "execute_intake_complete",
            "detail": result,
        }

    if node_id == EXECUTE_BRANCH_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        result = run_execute_branch_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not result.get("ok"):
            snapshot["status"] = "execution_error"
            return {
                "progressed": True,
                "reason": "execution_error",
                "error": result,
            }
        clear_run_wait(snapshot)
        return {
            "progressed": True,
            "reason": "execute_branch_complete",
            "detail": result,
        }

    if node_id == EXECUTE_PLAN_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        if visit_has_accepted_proceed_plan(
            snapshot,
            visit_id=str(visit.get("id")),
        ):
            result = run_execute_plan_complete(
                snapshot,
                visit,
                flow,
                workspace=workspace,
                foundry_bundle=foundry_bundle,
                run_dir=run_dir,
            )
            if not result.get("ok"):
                snapshot["status"] = "execution_error"
                return {
                    "progressed": True,
                    "reason": "execution_error",
                    "error": result,
                }
            clear_run_wait(snapshot)
            return {
                "progressed": True,
                "reason": "execute_plan_complete",
                "detail": result,
            }

    if node_id == EXECUTE_BUILD_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        result = run_execute_build_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not result.get("ok"):
            if result.get("reopened"):
                return {"progressed": True, "reason": "execute_build_reopened", "detail": result}
            snapshot["status"] = "execution_error"
            return {
                "progressed": True,
                "reason": "execution_error",
                "error": result,
            }
        clear_run_wait(snapshot)
        return {
            "progressed": True,
            "reason": "execute_build_complete",
            "detail": result,
        }

    if node_id == EXECUTE_TEST_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        result = run_execute_test_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not result.get("ok"):
            if result.get("reopened"):
                return {"progressed": True, "reason": "execute_test_reopened", "detail": result}
            snapshot["status"] = "execution_error"
            return {
                "progressed": True,
                "reason": "execution_error",
                "error": result,
            }
        clear_run_wait(snapshot)
        return {
            "progressed": True,
            "reason": "execute_test_complete",
            "detail": result,
        }

    if node_id == EXECUTE_COMMIT_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        result = run_execute_commit_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not result.get("ok"):
            snapshot["status"] = "execution_error"
            return {"progressed": True, "reason": "execution_error", "error": result}
        clear_run_wait(snapshot)
        return {"progressed": True, "reason": "execute_commit_complete", "detail": result}

    if node_id == VERIFY_INTAKE_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        result = run_verify_intake_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not result.get("ok"):
            snapshot["status"] = "execution_error"
            return {"progressed": True, "reason": "execution_error", "error": result}
        clear_run_wait(snapshot)
        return {"progressed": True, "reason": "verify_intake_complete", "detail": result}

    if node_id == VERIFY_ACCEPTANCE_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        if visit_has_accepted_task_result(
            snapshot,
            visit_id=str(visit.get("id")),
            task_id=VERIFY_ACCEPTANCE_TASK_ID,
        ):
            result = run_verify_acceptance_complete(
                snapshot,
                visit,
                flow,
                workspace=workspace,
                foundry_bundle=foundry_bundle,
                run_dir=run_dir,
            )
            if not result.get("ok"):
                snapshot["status"] = "execution_error"
                return {"progressed": True, "reason": "execution_error", "error": result}
            clear_run_wait(snapshot)
            return {"progressed": True, "reason": "verify_acceptance_complete", "detail": result}

    if node_id == VERIFY_CODE_QUALITY_NODE and str(visit.get("lifecycle")) in (
        LIFECYCLE_OPENED,
        "examined",
    ):
        result = run_verify_code_quality_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not result.get("ok"):
            snapshot["status"] = "execution_error"
            return {"progressed": True, "reason": "execution_error", "error": result}
        clear_run_wait(snapshot)
        return {"progressed": True, "reason": "verify_code_quality_complete", "detail": result}

    if node_id == VERIFY_CODE_REVIEW_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        result = run_verify_code_review_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not result.get("ok"):
            snapshot["status"] = "execution_error"
            return {"progressed": True, "reason": "execution_error", "error": result}
        clear_run_wait(snapshot)
        return {"progressed": True, "reason": "verify_code_review_complete", "detail": result}

    if node_id == VERIFY_COMPLETE_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        result = run_verify_complete_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not result.get("ok"):
            snapshot["status"] = "execution_error"
            return {"progressed": True, "reason": "execution_error", "error": result}
        clear_run_wait(snapshot)
        return {"progressed": True, "reason": "verify_complete_complete", "detail": result}

    if node_id == DELIVER_STUB_NODE and str(visit.get("lifecycle")) == LIFECYCLE_OPENED:
        result = run_deliver_stub_complete(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        if not result.get("ok"):
            snapshot["status"] = "execution_error"
            return {"progressed": True, "reason": "execution_error", "error": result}
        clear_run_wait(snapshot)
        if str(snapshot.get("status")) != "completed":
            snapshot["status"] = "completed"
        return {"progressed": True, "reason": "deliver_stub_complete", "detail": result}

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
