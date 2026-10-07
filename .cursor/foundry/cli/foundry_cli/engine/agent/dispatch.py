"""Persist agent requests and dispatch through adapters."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from foundry_cli.engine.agent.adapter import AgentAdapter, AgentAdapterEnvelope, get_adapter
from foundry_cli.engine.agent.tasks import (
    EXECUTE_PLAN_TASK_ID,
    SHAPE_EXAMINE_TASK_ID,
    SHAPE_PRESENT_TASK_ID,
    SHAPE_RECORD_TASK_ID,
    VERIFY_ACCEPTANCE_TASK_ID,
    build_agent_request,
)
from foundry_cli.ledger import append_event
from foundry_cli.util import now_iso


def agent_requests_map(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw = snapshot.get("agent_requests")
    if raw is None:
        raw = {}
        snapshot["agent_requests"] = raw
    if not isinstance(raw, dict):
        raise ValueError("snapshot.agent_requests must be an object")
    return raw


def find_request(snapshot: dict[str, Any], request_id: str) -> dict[str, Any] | None:
    record = agent_requests_map(snapshot).get(request_id)
    return record if isinstance(record, dict) else None


def visit_has_accepted_task_result(
    snapshot: dict[str, Any],
    *,
    visit_id: str,
    task_id: str,
) -> bool:
    accepted_seq: int | None = None
    superseded_after = False
    for event in snapshot.get("ledger") or []:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        payload = event.get("payload") or {}
        if event_type == "agent.result.accepted":
            if payload.get("visit_id") == visit_id and payload.get("task_id") == task_id:
                accepted_seq = int(event.get("seq") or 0)
                superseded_after = False
        elif event_type == "agent.result.superseded" and accepted_seq is not None:
            if payload.get("visit_id") == visit_id and payload.get("task_id") == task_id:
                if int(event.get("seq") or 0) > accepted_seq:
                    superseded_after = True
    return accepted_seq is not None and not superseded_after


def _accepted_result_for_task(
    snapshot: dict[str, Any],
    *,
    visit_id: str,
    task_id: str,
) -> dict[str, Any] | None:
    if not visit_has_accepted_task_result(snapshot, visit_id=visit_id, task_id=task_id):
        return None
    for record in agent_requests_map(snapshot).values():
        if not isinstance(record, dict):
            continue
        if (
            record.get("visit_id") == visit_id
            and record.get("task_id") == task_id
            and record.get("status") == "accepted"
        ):
            body = record.get("accepted_result")
            return body if isinstance(body, dict) else None
    return None


def visit_has_accepted_proceed_presentation(
    snapshot: dict[str, Any],
    *,
    visit_id: str,
) -> bool:
    result = _accepted_result_for_task(
        snapshot,
        visit_id=visit_id,
        task_id=SHAPE_PRESENT_TASK_ID,
    )
    return result is not None and result.get("verdict") == "PROCEED"


def visit_has_accepted_proceed_record(
    snapshot: dict[str, Any],
    *,
    visit_id: str,
) -> bool:
    result = _accepted_result_for_task(
        snapshot,
        visit_id=visit_id,
        task_id=SHAPE_RECORD_TASK_ID,
    )
    return result is not None and result.get("verdict") == "PROCEED"


def visit_has_accepted_proceed_plan(
    snapshot: dict[str, Any],
    *,
    visit_id: str,
) -> bool:
    result = _accepted_result_for_task(
        snapshot,
        visit_id=visit_id,
        task_id=EXECUTE_PLAN_TASK_ID,
    )
    return result is not None and result.get("verdict") == "PROCEED"


def ensure_shape_examine_request(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    foundry_bundle: Path,
    workspace: Path,
    run_dir: Path,
) -> str:
    """Return request_id; create ledger event when a new request is persisted."""
    visit_id = str(visit.get("id"))
    if visit_has_accepted_task_result(snapshot, visit_id=visit_id, task_id=SHAPE_EXAMINE_TASK_ID):
        raise RuntimeError("examination judgment already accepted")

    wait = snapshot.get("wait")
    if isinstance(wait, dict) and wait.get("kind") == "agent":
        ref = wait.get("request_ref")
        if isinstance(ref, str) and find_request(snapshot, ref):
            return ref

    for request_id, record in agent_requests_map(snapshot).items():
        if not isinstance(record, dict):
            continue
        if (
            record.get("visit_id") == visit_id
            and record.get("task_id") == SHAPE_EXAMINE_TASK_ID
            and record.get("status") in ("requested", "dispatched")
        ):
            return str(request_id)

    request = build_agent_request(
        snapshot,
        visit,
        flow,
        task_id=SHAPE_EXAMINE_TASK_ID,
        foundry_bundle=foundry_bundle,
        workspace=workspace,
        run_dir=run_dir,
    )
    request_id = str(request["request_id"])
    agent_requests_map(snapshot)[request_id] = deepcopy(request)
    append_event(
        snapshot,
        event_type="agent.requested",
        visit_id=visit_id,
        node_id=str(visit.get("node_id")),
        payload={
            "request_id": request_id,
            "task_id": SHAPE_EXAMINE_TASK_ID,
            "attempt": request.get("attempt"),
            "definition_digest": request.get("definition_digest"),
            "input_digest": request.get("input_digest"),
        },
    )
    return request_id


def ensure_shape_present_request(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    foundry_bundle: Path,
    workspace: Path,
    run_dir: Path,
) -> str:
    """Return request_id; create ledger event when a new request is persisted."""
    visit_id = str(visit.get("id"))
    if visit_has_accepted_proceed_presentation(snapshot, visit_id=visit_id):
        raise RuntimeError("presentation judgment already accepted with PROCEED")

    wait = snapshot.get("wait")
    if isinstance(wait, dict) and wait.get("kind") == "agent":
        ref = wait.get("request_ref")
        if isinstance(ref, str) and find_request(snapshot, ref):
            return ref

    for request_id, record in agent_requests_map(snapshot).items():
        if not isinstance(record, dict):
            continue
        if (
            record.get("visit_id") == visit_id
            and record.get("task_id") == SHAPE_PRESENT_TASK_ID
            and record.get("status") in ("requested", "dispatched")
        ):
            return str(request_id)

    request = build_agent_request(
        snapshot,
        visit,
        flow,
        task_id=SHAPE_PRESENT_TASK_ID,
        foundry_bundle=foundry_bundle,
        workspace=workspace,
        run_dir=run_dir,
    )
    request_id = str(request["request_id"])
    agent_requests_map(snapshot)[request_id] = deepcopy(request)
    append_event(
        snapshot,
        event_type="agent.requested",
        visit_id=visit_id,
        node_id=str(visit.get("node_id")),
        payload={
            "request_id": request_id,
            "task_id": SHAPE_PRESENT_TASK_ID,
            "attempt": request.get("attempt"),
            "definition_digest": request.get("definition_digest"),
            "input_digest": request.get("input_digest"),
        },
    )
    return request_id


def ensure_shape_record_request(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    foundry_bundle: Path,
    workspace: Path,
    run_dir: Path,
) -> str:
    """Return request_id; create ledger event when a new request is persisted."""
    visit_id = str(visit.get("id"))
    if visit_has_accepted_proceed_record(snapshot, visit_id=visit_id):
        raise RuntimeError("record judgment already accepted with PROCEED")

    wait = snapshot.get("wait")
    if isinstance(wait, dict) and wait.get("kind") == "agent":
        ref = wait.get("request_ref")
        if isinstance(ref, str) and find_request(snapshot, ref):
            return ref

    for request_id, record in agent_requests_map(snapshot).items():
        if not isinstance(record, dict):
            continue
        if (
            record.get("visit_id") == visit_id
            and record.get("task_id") == SHAPE_RECORD_TASK_ID
            and record.get("status") in ("requested", "dispatched")
        ):
            return str(request_id)

    request = build_agent_request(
        snapshot,
        visit,
        flow,
        task_id=SHAPE_RECORD_TASK_ID,
        foundry_bundle=foundry_bundle,
        workspace=workspace,
        run_dir=run_dir,
    )
    request_id = str(request["request_id"])
    agent_requests_map(snapshot)[request_id] = deepcopy(request)
    append_event(
        snapshot,
        event_type="agent.requested",
        visit_id=visit_id,
        node_id=str(visit.get("node_id")),
        payload={
            "request_id": request_id,
            "task_id": SHAPE_RECORD_TASK_ID,
            "attempt": request.get("attempt"),
            "definition_digest": request.get("definition_digest"),
            "input_digest": request.get("input_digest"),
        },
    )
    return request_id


def ensure_verify_acceptance_request(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    foundry_bundle: Path,
    workspace: Path,
    run_dir: Path,
) -> str:
    """Return request_id; create ledger event when a new request is persisted."""
    visit_id = str(visit.get("id"))
    if visit_has_accepted_task_result(snapshot, visit_id=visit_id, task_id=VERIFY_ACCEPTANCE_TASK_ID):
        raise RuntimeError("verify acceptance judgment already accepted")

    wait = snapshot.get("wait")
    if isinstance(wait, dict) and wait.get("kind") == "agent":
        ref = wait.get("request_ref")
        if isinstance(ref, str) and find_request(snapshot, ref):
            return ref

    for request_id, record in agent_requests_map(snapshot).items():
        if not isinstance(record, dict):
            continue
        if (
            record.get("visit_id") == visit_id
            and record.get("task_id") == VERIFY_ACCEPTANCE_TASK_ID
            and record.get("status") in ("requested", "dispatched")
        ):
            return str(request_id)

    request = build_agent_request(
        snapshot,
        visit,
        flow,
        task_id=VERIFY_ACCEPTANCE_TASK_ID,
        foundry_bundle=foundry_bundle,
        workspace=workspace,
        run_dir=run_dir,
    )
    request_id = str(request["request_id"])
    agent_requests_map(snapshot)[request_id] = deepcopy(request)
    append_event(
        snapshot,
        event_type="agent.requested",
        visit_id=visit_id,
        node_id=str(visit.get("node_id")),
        payload={
            "request_id": request_id,
            "task_id": VERIFY_ACCEPTANCE_TASK_ID,
            "attempt": request.get("attempt"),
            "definition_digest": request.get("definition_digest"),
            "input_digest": request.get("input_digest"),
        },
    )
    return request_id


def ensure_execute_plan_request(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    foundry_bundle: Path,
    workspace: Path,
    run_dir: Path,
) -> str:
    """Return request_id; create ledger event when a new request is persisted."""
    visit_id = str(visit.get("id"))
    if visit_has_accepted_proceed_plan(snapshot, visit_id=visit_id):
        raise RuntimeError("plan judgment already accepted with PROCEED")

    wait = snapshot.get("wait")
    if isinstance(wait, dict) and wait.get("kind") == "agent":
        ref = wait.get("request_ref")
        if isinstance(ref, str) and find_request(snapshot, ref):
            return ref

    for request_id, record in agent_requests_map(snapshot).items():
        if not isinstance(record, dict):
            continue
        if (
            record.get("visit_id") == visit_id
            and record.get("task_id") == EXECUTE_PLAN_TASK_ID
            and record.get("status") in ("requested", "dispatched")
        ):
            return str(request_id)

    request = build_agent_request(
        snapshot,
        visit,
        flow,
        task_id=EXECUTE_PLAN_TASK_ID,
        foundry_bundle=foundry_bundle,
        workspace=workspace,
        run_dir=run_dir,
    )
    request_id = str(request["request_id"])
    agent_requests_map(snapshot)[request_id] = deepcopy(request)
    append_event(
        snapshot,
        event_type="agent.requested",
        visit_id=visit_id,
        node_id=str(visit.get("node_id")),
        payload={
            "request_id": request_id,
            "task_id": EXECUTE_PLAN_TASK_ID,
            "attempt": request.get("attempt"),
            "definition_digest": request.get("definition_digest"),
            "input_digest": request.get("input_digest"),
        },
    )
    return request_id


def mark_dispatched(snapshot: dict[str, Any], request_id: str, envelope: AgentAdapterEnvelope) -> None:
    record = find_request(snapshot, request_id)
    if record is None:
        return
    if record.get("status") == "accepted":
        return
    record["status"] = "dispatched"
    record["dispatched_at"] = now_iso()
    record["provider_request_id"] = envelope.provider_request_id
    record["finish_reason"] = envelope.finish_reason
    append_event(
        snapshot,
        event_type="agent.dispatched",
        visit_id=record.get("visit_id"),
        payload={
            "request_id": request_id,
            "provider_request_id": envelope.provider_request_id,
            "finish_reason": envelope.finish_reason,
            "attempt": envelope.attempt,
        },
    )


def stage_agent_dispatch_outbox(snapshot: dict[str, Any], request_id: str) -> None:
    """Mark a durable outbox entry before any external adapter call."""
    record = find_request(snapshot, request_id)
    if record is None:
        return
    if record.get("status") == "accepted":
        return
    if isinstance(record.get("dispatch_outbox"), dict):
        return
    record["status"] = "requested"
    record["dispatch_outbox"] = {"status": "pending", "request_id": request_id}
    append_event(
        snapshot,
        event_type="agent.dispatch.outbox",
        visit_id=record.get("visit_id"),
        payload={"request_id": request_id, "status": "pending"},
    )


def dispatch_pending_agent_request(
    snapshot: dict[str, Any],
    request_id: str,
    *,
    adapter: AgentAdapter | None = None,
) -> AgentAdapterEnvelope | None:
    record = find_request(snapshot, request_id)
    if record is None:
        return None
    if record.get("status") == "accepted":
        return None
    if record.get("status") == "dispatched" and record.get("pending_envelope"):
        pending = record.get("pending_envelope")
        if isinstance(pending, dict):
            return AgentAdapterEnvelope(
                request_id=str(pending["request_id"]),
                attempt=int(pending.get("attempt") or 1),
                provider_request_id=str(pending.get("provider_request_id") or ""),
                raw_response_ref=pending.get("raw_response_ref"),
                usage=pending.get("usage") if isinstance(pending.get("usage"), dict) else {},
                finish_reason=str(pending.get("finish_reason") or "stop"),
                result=pending["result"],
            )
    if record.get("pending_envelope"):
        pending = record.get("pending_envelope")
        if isinstance(pending, dict):
            return AgentAdapterEnvelope(
                request_id=str(pending["request_id"]),
                attempt=int(pending.get("attempt") or 1),
                provider_request_id=str(pending.get("provider_request_id") or ""),
                raw_response_ref=pending.get("raw_response_ref"),
                usage=pending.get("usage") if isinstance(pending.get("usage"), dict) else {},
                finish_reason=str(pending.get("finish_reason") or "stop"),
                result=pending["result"],
            )
    adapter = adapter or get_adapter()
    envelope = adapter.invoke(record)
    mark_dispatched(snapshot, request_id, envelope)
    outbox = record.get("dispatch_outbox")
    if isinstance(outbox, dict):
        outbox["status"] = "completed"
    record["pending_envelope"] = {
        "request_id": envelope.request_id,
        "attempt": envelope.attempt,
        "provider_request_id": envelope.provider_request_id,
        "raw_response_ref": envelope.raw_response_ref,
        "usage": envelope.usage,
        "finish_reason": envelope.finish_reason,
        "result": envelope.result,
    }
    return envelope


def dispatch_for_agent_wait(
    snapshot: dict[str, Any],
    *,
    adapter: AgentAdapter | None = None,
) -> AgentAdapterEnvelope | None:
    wait = snapshot.get("wait")
    if not isinstance(wait, dict) or wait.get("kind") != "agent":
        return None
    ref = wait.get("request_ref")
    if not isinstance(ref, str):
        return None
    return dispatch_pending_agent_request(snapshot, ref, adapter=adapter)


def try_accept_agent_envelope(
    snapshot: dict[str, Any],
    envelope: AgentAdapterEnvelope | None,
    *,
    foundry_bundle: Path,
) -> dict[str, Any] | None:
    """Validate a synchronous adapter envelope and accept it when still on agent wait."""
    if envelope is None:
        return None
    result = envelope.result
    if not isinstance(result, dict):
        return None
    wait = snapshot.get("wait")
    if not isinstance(wait, dict) or wait.get("kind") != "agent":
        record = find_request(snapshot, envelope.request_id)
        if record is not None and record.get("status") == "accepted":
            return {
                "ok": True,
                "idempotent": True,
                "request_id": envelope.request_id,
            }
        return None
    from foundry_cli.engine.agent.submit import submit_agent_result

    active = snapshot.get("active_visit")
    visit_dict = active if isinstance(active, dict) else None
    return submit_agent_result(
        snapshot,
        request_id=envelope.request_id,
        result=result,
        foundry_bundle=foundry_bundle,
        visit=visit_dict,
    )
