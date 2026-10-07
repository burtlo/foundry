"""Validate and accept agent results (engine-owned state patches)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from foundry_cli.engine.agent.dispatch import (
    _accepted_result_for_task,
    find_request,
    visit_has_accepted_task_result,
)
from foundry_cli.engine.agent.tasks import (
    EXAMINATION_RESULT_SCHEMA_FILE,
    EXECUTE_PLAN_TASK_ID,
    SHAPE_EXAMINE_TASK_ID,
    SHAPE_PRESENT_TASK_ID,
    SHAPE_RECORD_TASK_ID,
    VERIFY_ACCEPTANCE_TASK_ID,
    output_schema_file,
)
from foundry_cli.engine.wait_state import clear_run_wait, set_run_wait
from foundry_cli.engine.examination_state import (
    derive_open_clarifying_questions_count,
    sync_open_clarifying_questions_count,
)
from foundry_cli.ledger import append_event
from foundry_cli.validate import validate_payload


def _format_draft_ac(criteria: list[str]) -> str:
    lines = [line.strip() for line in criteria if isinstance(line, str) and line.strip()]
    return "\n".join(lines)


_ACCEPTANCE_DECISIONS = frozenset({"pass", "replan", "reshape", "rework_execute"})


def _validate_verify_acceptance_semantics(result: dict[str, Any]) -> str | None:
    decision = str(result.get("gate_decision") or "").strip().lower()
    if decision not in _ACCEPTANCE_DECISIONS:
        return "gate_decision must be pass, replan, reshape, or rework_execute"
    evidence_ok = result.get("evidence_ok")
    if decision == "pass" and evidence_ok is not True:
        return "evidence_ok must be true when gate_decision is pass"
    if decision != "pass" and evidence_ok is True:
        return "evidence_ok must be false unless gate_decision is pass"
    items = result.get("items")
    if not isinstance(items, list) or not items:
        return "items must be a non-empty array"
    return None


def apply_examination_result(snapshot: dict[str, Any], result: dict[str, Any]) -> None:
    state = snapshot.setdefault("state", {})
    if not isinstance(state, dict):
        state = {}
        snapshot["state"] = state
    state["draft_ac"] = _format_draft_ac(list(result.get("draft_acceptance_criteria") or []))
    state["assumptions"] = list(result.get("assumptions") or [])
    questions_out: list[dict[str, Any]] = []
    for item in result.get("questions") or []:
        if not isinstance(item, dict):
            continue
        questions_out.append(
            {
                "id": str(item.get("id")),
                "text": str(item.get("text")),
                "why_needed": str(item.get("why_needed")),
                "status": "open",
            }
        )
    state["clarifying_questions"] = questions_out
    decisions_out: list[dict[str, Any]] = []
    for item in result.get("decisions") or []:
        if not isinstance(item, dict):
            continue
        decisions_out.append({"text": str(item.get("text")), "basis": str(item.get("basis"))})
    state["examination_decisions"] = decisions_out
    sync_open_clarifying_questions_count(snapshot)


def _wait_matches_request(snapshot: dict[str, Any], request_id: str) -> bool:
    wait = snapshot.get("wait")
    if not isinstance(wait, dict):
        return False
    return wait.get("kind") == "agent" and wait.get("request_ref") == request_id


def submit_agent_result(
    snapshot: dict[str, Any],
    *,
    request_id: str,
    result: dict[str, Any],
    foundry_bundle: Path,
    visit: dict[str, Any] | None = None,
    flow: dict[str, Any] | None = None,
    run_dir: Path | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    record = find_request(snapshot, request_id)
    if record is None:
        return {"ok": False, "code": "REQUEST_NOT_FOUND", "message": f"Unknown agent request {request_id}"}

    visit_id = str(record.get("visit_id"))
    task_id = str(record.get("task_id"))

    if record.get("status") == "accepted":
        return {
            "ok": True,
            "idempotent": True,
            "request_id": request_id,
            "visit_id": visit_id,
            "task_id": task_id,
        }

    if visit_has_accepted_task_result(snapshot, visit_id=visit_id, task_id=task_id):
        prior = _accepted_result_for_task(snapshot, visit_id=visit_id, task_id=task_id)
        if (
            task_id in (SHAPE_PRESENT_TASK_ID, SHAPE_RECORD_TASK_ID, EXECUTE_PLAN_TASK_ID)
            and prior is not None
            and prior.get("verdict") == "BLOCKED"
        ):
            append_event(
                snapshot,
                event_type="agent.result.superseded",
                visit_id=visit_id,
                payload={
                    "task_id": task_id,
                    "visit_id": visit_id,
                    "reason": "judgment_retry_after_blocked",
                },
            )
            for rid, rec in (snapshot.get("agent_requests") or {}).items():
                if not isinstance(rec, dict):
                    continue
                if rec.get("visit_id") == visit_id and rec.get("task_id") == task_id:
                    if rec.get("status") == "accepted":
                        rec["status"] = "superseded"
        else:
            return {
                "ok": False,
                "code": "REQUEST_SUPERSEDED",
                "message": "A result for this visit task was already accepted",
            }

    active = snapshot.get("active_visit")
    if not isinstance(active, dict) or str(active.get("id")) != visit_id:
        return {"ok": False, "code": "VISIT_MISMATCH", "message": "Active visit does not match request"}

    if not _wait_matches_request(snapshot, request_id):
        return {
            "ok": False,
            "code": "WAIT_MISMATCH",
            "message": "Run is not waiting on this agent request",
        }

    schema_file = output_schema_file(record, foundry_bundle)
    errors = validate_payload(result, schema_file, foundry_bundle)
    if errors:
        append_event(
            snapshot,
            event_type="agent.result.rejected",
            visit_id=visit_id,
            payload={"request_id": request_id, "errors": errors},
        )
        return {
            "ok": False,
            "code": "RESULT_VALIDATION_FAILED",
            "message": "Agent result failed schema validation",
            "errors": errors,
        }

    if task_id == SHAPE_EXAMINE_TASK_ID:
        question_ids = [str(q.get("id")) for q in result.get("questions") or [] if isinstance(q, dict)]
        if len(question_ids) != len(set(question_ids)):
            return {
                "ok": False,
                "code": "RESULT_VALIDATION_FAILED",
                "message": "Question ids must be unique within the result",
            }

    if task_id == VERIFY_ACCEPTANCE_TASK_ID:
        semantic_error = _validate_verify_acceptance_semantics(result)
        if semantic_error:
            return {
                "ok": False,
                "code": "RESULT_VALIDATION_FAILED",
                "message": semantic_error,
            }

    if task_id == SHAPE_EXAMINE_TASK_ID:
        apply_examination_result(snapshot, result)

    if task_id == SHAPE_PRESENT_TASK_ID:
        verdict = str(result.get("verdict") or "")
        if verdict == "BLOCKED":
            if visit is None or run_dir is None:
                return {
                    "ok": False,
                    "code": "INTERNAL",
                    "message": "BLOCKED presentation submit requires visit and run_dir",
                }
            from foundry_cli.engine.shape_step_executor import seal_presentation_blocked_receipt

            record["status"] = "accepted"
            record["accepted_result"] = deepcopy(result)
            append_event(
                snapshot,
                event_type="agent.result.accepted",
                visit_id=visit_id,
                node_id=str(active.get("node_id")),
                payload={
                    "request_id": request_id,
                    "task_id": task_id,
                    "visit_id": visit_id,
                    "output_schema": schema_file,
                },
            )
            seal_result = seal_presentation_blocked_receipt(
                snapshot,
                visit,
                result=result,
                run_dir=run_dir,
                foundry_bundle=foundry_bundle,
            )
            clear_run_wait(snapshot)
            if not seal_result.get("ok"):
                return seal_result
            return {
                "ok": True,
                "request_id": request_id,
                "visit_id": visit_id,
                "task_id": task_id,
                "verdict": verdict,
                "wait": snapshot.get("wait"),
            }

    if task_id == SHAPE_RECORD_TASK_ID:
        verdict = str(result.get("verdict") or "")
        if verdict == "BLOCKED":
            if visit is None or run_dir is None:
                return {
                    "ok": False,
                    "code": "INTERNAL",
                    "message": "BLOCKED record submit requires visit and run_dir",
                }
            from foundry_cli.engine.shape_step_executor import seal_record_blocked_receipt

            record["status"] = "accepted"
            record["accepted_result"] = deepcopy(result)
            append_event(
                snapshot,
                event_type="agent.result.accepted",
                visit_id=visit_id,
                node_id=str(active.get("node_id")),
                payload={
                    "request_id": request_id,
                    "task_id": task_id,
                    "visit_id": visit_id,
                    "output_schema": schema_file,
                },
            )
            seal_result = seal_record_blocked_receipt(
                snapshot,
                visit,
                result=result,
                run_dir=run_dir,
                foundry_bundle=foundry_bundle,
            )
            clear_run_wait(snapshot)
            if not seal_result.get("ok"):
                return seal_result
            return {
                "ok": True,
                "request_id": request_id,
                "visit_id": visit_id,
                "task_id": task_id,
                "verdict": verdict,
                "wait": snapshot.get("wait"),
            }

    if task_id == EXECUTE_PLAN_TASK_ID:
        verdict = str(result.get("verdict") or "")
        if verdict == "BLOCKED":
            if visit is None or run_dir is None:
                return {
                    "ok": False,
                    "code": "INTERNAL",
                    "message": "BLOCKED plan submit requires visit and run_dir",
                }
            from foundry_cli.engine.execute_step_executor import seal_plan_blocked_receipt

            record["status"] = "accepted"
            record["accepted_result"] = deepcopy(result)
            append_event(
                snapshot,
                event_type="agent.result.accepted",
                visit_id=visit_id,
                node_id=str(active.get("node_id")),
                payload={
                    "request_id": request_id,
                    "task_id": task_id,
                    "visit_id": visit_id,
                    "output_schema": schema_file,
                },
            )
            seal_result = seal_plan_blocked_receipt(
                snapshot,
                visit,
                result=result,
                run_dir=run_dir,
                foundry_bundle=foundry_bundle,
            )
            clear_run_wait(snapshot)
            if not seal_result.get("ok"):
                return seal_result
            return {
                "ok": True,
                "request_id": request_id,
                "visit_id": visit_id,
                "task_id": task_id,
                "verdict": verdict,
                "wait": snapshot.get("wait"),
            }

    record["status"] = "accepted"
    record["accepted_result"] = deepcopy(result)
    append_event(
        snapshot,
        event_type="agent.result.accepted",
        visit_id=visit_id,
        node_id=str(active.get("node_id")),
        payload={
            "request_id": request_id,
            "task_id": task_id,
            "visit_id": visit_id,
            "output_schema": schema_file,
        },
    )

    if task_id == SHAPE_EXAMINE_TASK_ID:
        open_count = derive_open_clarifying_questions_count(snapshot.get("state") or {})
        if open_count > 0:
            set_run_wait(
                snapshot,
                kind="user_input",
                visit_id=visit_id,
                summary=f"{open_count} clarifying question(s) need answers",
                request_ref=f"questions:{visit_id}",
            )
        else:
            clear_run_wait(snapshot)
        return {
            "ok": True,
            "request_id": request_id,
            "visit_id": visit_id,
            "task_id": task_id,
            "open_clarifying_questions_count": open_count,
            "wait": snapshot.get("wait"),
        }

    clear_run_wait(snapshot)
    return {
        "ok": True,
        "request_id": request_id,
        "visit_id": visit_id,
        "task_id": task_id,
        "wait": snapshot.get("wait"),
    }
