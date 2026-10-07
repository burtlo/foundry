"""Operator-directed run control (execute start, retry, cancel)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.constants import (
    EVENT_EXECUTE_AUTHORIZATION_RECORDED,
    EVENT_OPERATOR_ACTION,
    EVENT_RUN_STATUS_CHANGED,
    RUN_STATUS_RUNNING,
)
from foundry_cli.engine.advance import TERMINAL_RUN_STATUSES
from foundry_cli.engine.gates import decide_gate
from foundry_cli.engine.run_status_reason import clear_status_reason, status_reason_payload
from foundry_cli.engine.wait_state import clear_run_wait
from foundry_cli.ledger import append_event, ledger_events
from foundry_cli.run_store import get_revision

EXECUTE_START_NODE_ID = "execute.start"
EXECUTE_START_DECISION = "accept"


def _shape_record_sealed(snapshot: dict[str, Any]) -> bool:
    for event in ledger_events(snapshot):
        if not isinstance(event, dict):
            continue
        if event.get("type") == "visit.sealed" and event.get("node_id") == "shape.record":
            return True
    return False


def execute_start_authorization(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any]:
    """Record explicit execute authorization and accept the execute.start gate."""
    node_id = str(visit.get("node_id") or "")
    if node_id != EXECUTE_START_NODE_ID:
        return {
            "ok": False,
            "code": "EXECUTE_START_GATE_REQUIRED",
            "message": (
                f"foundry start is only valid at {EXECUTE_START_NODE_ID!r}; "
                f"active node is {node_id!r}"
            ),
            "active_node_id": node_id,
        }

    if str(snapshot.get("status")) in TERMINAL_RUN_STATUSES:
        return {
            "ok": False,
            "code": "RUN_TERMINAL",
            "message": f"Run status is {snapshot.get('status')!r}",
        }

    wait = snapshot.get("wait")
    if not isinstance(wait, dict) or str(wait.get("kind") or "") != "decision":
        wait_kind = wait.get("kind") if isinstance(wait, dict) else None
        return {
            "ok": False,
            "code": "WAIT_KIND_MISMATCH",
            "message": "Execute start requires an active decision wait at execute.start",
            "wait_kind": wait_kind,
        }

    if not _shape_record_sealed(snapshot):
        return {
            "ok": False,
            "code": "SHAPE_NOT_RECORDED",
            "message": "Shape record must be sealed before execute authorization",
        }

    visit_id = str(visit.get("id") or "")
    append_event(
        snapshot,
        event_type=EVENT_EXECUTE_AUTHORIZATION_RECORDED,
        visit_id=visit_id,
        node_id=node_id,
        payload={"decision": EXECUTE_START_DECISION, "authorized": True},
    )

    result = decide_gate(
        snapshot,
        visit,
        flow,
        decision=EXECUTE_START_DECISION,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not result.get("ok"):
        return result
    clear_run_wait(snapshot)
    result["authorization_recorded"] = True
    return result


def retry_run(snapshot: dict[str, Any], *, reason: str | None = None) -> dict[str, Any]:
    """Resume a halted or errored run, or clear an operator wait for retry.

    When ``status_reason`` is set with ``retry_eligible: true`` (repair/reverify
    loop limits, missing engine evidence, etc.), retry clears the reason and
    returns the run to ``running`` so ``run advance`` can continue.
    """
    status = str(snapshot.get("status") or "")
    wait = snapshot.get("wait")
    wait_kind = str(wait.get("kind") or "") if isinstance(wait, dict) else ""

    reason_info = status_reason_payload(snapshot)
    recoverable_status = status in {"halted", "execution_error", "paused"}
    recoverable_wait = wait_kind == "operator"
    recoverable_reason = bool(reason_info and reason_info.get("retry_eligible"))
    if not recoverable_status and not recoverable_wait and not recoverable_reason:
        return {
            "ok": False,
            "code": "RETRY_NOT_ALLOWED",
            "message": (
                "Retry is only allowed for halted, execution_error, or paused runs, "
                "or when waiting for operator action"
            ),
            "status": status,
            "wait_kind": wait_kind or None,
        }

    if status in TERMINAL_RUN_STATUSES and status not in {"halted", "execution_error", "paused"}:
        return {
            "ok": False,
            "code": "RUN_TERMINAL",
            "message": f"Run status is {status!r}",
        }

    prior = status
    if prior != RUN_STATUS_RUNNING:
        snapshot["status"] = RUN_STATUS_RUNNING
        append_event(
            snapshot,
            event_type=EVENT_RUN_STATUS_CHANGED,
            payload={
                "prior_status": prior,
                "new_status": RUN_STATUS_RUNNING,
                "reason": reason or "operator_retry",
            },
        )

    append_event(
        snapshot,
        event_type=EVENT_OPERATOR_ACTION,
        payload={"action": "retry", "reason": reason, "prior_status": prior},
    )
    cleared_reason = status_reason_payload(snapshot)
    clear_status_reason(snapshot)
    clear_run_wait(snapshot)
    return {
        "ok": True,
        "prior_status": prior,
        "status": RUN_STATUS_RUNNING,
        "revision": get_revision(snapshot),
        "cleared_status_reason": cleared_reason,
    }


def cancel_run(snapshot: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """Halt a non-terminal run with a recorded operator cancel reason."""
    status = str(snapshot.get("status") or "")
    if status in TERMINAL_RUN_STATUSES:
        return {
            "ok": False,
            "code": "RUN_TERMINAL",
            "message": f"Run is already terminal ({status!r})",
        }

    text = reason.strip()
    if not text:
        return {
            "ok": False,
            "code": "REASON_REQUIRED",
            "message": "cancel requires a non-empty --reason",
        }

    prior = status
    snapshot["status"] = "halted"
    append_event(
        snapshot,
        event_type=EVENT_OPERATOR_ACTION,
        payload={"action": "cancel", "reason": text},
    )
    append_event(
        snapshot,
        event_type=EVENT_RUN_STATUS_CHANGED,
        payload={
            "prior_status": prior,
            "new_status": "halted",
            "reason": f"operator_cancel: {text}",
        },
    )
    clear_run_wait(snapshot)
    return {
        "ok": True,
        "prior_status": prior,
        "status": "halted",
        "reason": text,
    }
