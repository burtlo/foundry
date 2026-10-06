"""Shared run read/mutate operations for CLI and job host."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from foundry_cli.app_manifest import validate_manifest
from foundry_cli.constants import (
    DEFAULT_ENTRY_NODE_ID,
    DEFAULT_FLOW_ID,
    EVENT_RUN_STATUS_CHANGED,
    RUN_STATUS_NEW,
    RUN_STATUS_RUNNING,
)
from foundry_cli.engine import RUN_UUID_KEY, admit_visit, decide_gate, generate_run_slug
from foundry_cli.engine.advance import TERMINAL_RUN_STATUSES, advance_run
from foundry_cli.engine.agent.adapter import AgentAdapter
from foundry_cli.engine.agent.dispatch import (
    dispatch_for_agent_wait,
    stage_agent_dispatch_outbox,
    try_accept_agent_envelope,
)
from foundry_cli.engine.examination_state import submit_clarifying_answers
from foundry_cli.engine.agent.submit import submit_agent_result
from foundry_cli.engine.operator import (
    cancel_run,
    execute_start_authorization,
    retry_run,
)
from foundry_cli.engine.wait_state import clear_run_wait
from foundry_cli.errors import error, from_engine_result, ok
from foundry_cli.ledger import append_event, filter_events, ledger_events
from foundry_cli.registry import load_registry
from foundry_cli.run_store import (
    REVISION_KEY,
    RunStoreError,
    commit_snapshot,
    get_revision,
    load_snapshot,
    resolve_run_dir,
)


def _find_visit(snapshot: dict[str, Any], visit_id: str) -> dict[str, Any] | None:
    active = snapshot.get("active_visit")
    if isinstance(active, dict) and active.get("id") == visit_id:
        return active
    for visit in snapshot.get("visits") or []:
        if isinstance(visit, dict) and visit.get("id") == visit_id:
            return visit
    return None


def create_run(
    *,
    workspace: Path,
    bundle: Path,
    work_prompt: str | None = None,
    flow_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Create a run directory, admit the flow entry visit, persist work_prompt when provided."""
    flow_id = flow_id or DEFAULT_FLOW_ID
    try:
        _, flow = load_registry(bundle, flow_id=flow_id)
    except ValueError as exc:
        return error("INVALID_FLOW", str(exc))

    entry_node_id = str(flow.get("entry", DEFAULT_ENTRY_NODE_ID))
    manifest = validate_manifest(workspace, bundle)
    manifest_id = manifest.get("manifest_id") if isinstance(manifest.get("manifest_id"), str) else None
    run_id = run_id or generate_run_slug(workspace, manifest_id)
    run_dir = workspace / ".foundry" / "runs" / run_id
    if run_dir.exists():
        return error("RUN_EXISTS", f"Run directory already exists: {run_dir}")

    run_dir.mkdir(parents=True)
    (run_dir / "artifacts").mkdir(exist_ok=True)
    (run_dir / "receipts").mkdir(exist_ok=True)

    snapshot: dict[str, Any] = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        RUN_UUID_KEY: str(uuid.uuid4()),
        "flow_id": flow_id,
        "status": RUN_STATUS_RUNNING,
        "workspace": str(workspace),
        "config": {"workspace": str(workspace)},
        "state": {"ticket": None, "app_folder": None},
        "visits": [],
        "ledger": [],
        "wait": None,
    }
    if work_prompt is not None:
        if not str(work_prompt).strip():
            return error("INPUT_REQUIRED", "work_prompt must not be empty")
        config = snapshot["config"]
        if isinstance(config, dict):
            config["shape"] = {"work_prompt": work_prompt}

    append_event(
        snapshot,
        event_type=EVENT_RUN_STATUS_CHANGED,
        payload={"prior_status": RUN_STATUS_NEW, "new_status": RUN_STATUS_RUNNING},
    )

    visit = admit_visit(
        snapshot,
        node_id=entry_node_id,
        flow=flow,
        source="entry",
        workspace=workspace,
        foundry_bundle=bundle,
        run_dir=run_dir,
    )
    snapshot["active_visit"] = visit
    snapshot[REVISION_KEY] = 0
    snapshot["wait"] = None
    initial_revision = commit_snapshot(run_dir, snapshot, expected_revision=0, bump=True)

    return ok(
        run_id=run_id,
        flow_id=flow_id,
        status=str(snapshot.get("status")),
        entry_node_id=entry_node_id,
        active_visit_id=visit.get("id"),
        active_lifecycle=visit.get("lifecycle"),
        active_node_id=visit.get("node_id"),
        run_dir=str(run_dir),
        revision=initial_revision,
        work_prompt=work_prompt,
    )


def list_runs(workspace: Path) -> dict[str, Any]:
    runs_root = workspace / ".foundry" / "runs"
    if not runs_root.is_dir():
        return ok(runs=[])
    summaries: list[dict[str, Any]] = []
    for child in sorted(runs_root.iterdir()):
        if not child.is_dir():
            continue
        snapshot_path = child / "snapshot.json"
        if not snapshot_path.is_file():
            continue
        try:
            snapshot = load_snapshot(child)
        except RunStoreError:
            continue
        active = snapshot.get("active_visit") if isinstance(snapshot.get("active_visit"), dict) else {}
        wait = snapshot.get("wait")
        summaries.append(
            {
                "run_id": snapshot.get("run_id") or child.name,
                "status": snapshot.get("status"),
                "revision": get_revision(snapshot),
                "active_visit_id": active.get("id"),
                "active_node_id": active.get("node_id"),
                "wait_kind": wait.get("kind") if isinstance(wait, dict) else None,
                "run_dir": str(child),
            }
        )
    return ok(runs=summaries)


def get_run(
    workspace: Path,
    *,
    run_id: str | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
        snapshot = load_snapshot(resolved)
    except RunStoreError as exc:
        return error(exc.code, exc.message)
    active = snapshot.get("active_visit") if isinstance(snapshot.get("active_visit"), dict) else {}
    return ok(
        run_id=snapshot.get("run_id"),
        revision=get_revision(snapshot),
        status=snapshot.get("status"),
        wait=snapshot.get("wait"),
        active_visit_id=active.get("id"),
        active_node_id=active.get("node_id"),
        active_lifecycle=active.get("lifecycle"),
        run_dir=str(resolved),
    )


def run_events(
    workspace: Path,
    *,
    run_id: str | None = None,
    run_dir: Path | None = None,
    after_seq: int = 0,
) -> dict[str, Any]:
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
        snapshot = load_snapshot(resolved)
    except RunStoreError as exc:
        return error(exc.code, exc.message)
    events = filter_events(snapshot, from_seq=after_seq + 1 if after_seq else None)
    return ok(
        run_id=snapshot.get("run_id"),
        revision=get_revision(snapshot),
        after_seq=after_seq,
        events=events,
    )


def advance_run_durable(
    *,
    workspace: Path,
    bundle: Path,
    run_id: str | None = None,
    run_dir: Path | None = None,
    flow_id: str | None = None,
    expected_revision: int | None = None,
    step_budget: int = 8,
    agent_adapter: AgentAdapter | None = None,
) -> dict[str, Any]:
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)

    try:
        snapshot = load_snapshot(resolved)
        revision_before = get_revision(snapshot)
        if expected_revision is not None and revision_before != expected_revision:
            return error(
                "STALE_REVISION",
                f"Expected revision {expected_revision}, found {revision_before}",
                revision=revision_before,
            )
        if not flow_id:
            flow_id = str(snapshot.get("flow_id") or DEFAULT_FLOW_ID)
        _, flow = load_registry(bundle, flow_id=flow_id)
        ledger_before = len(ledger_events(snapshot))
        advance_result = advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=bundle,
            run_dir=resolved,
            step_budget=step_budget,
        )
        revision_cursor = revision_before
        wait = snapshot.get("wait")
        if isinstance(wait, dict) and wait.get("kind") == "agent":
            request_ref = wait.get("request_ref")
            if isinstance(request_ref, str):
                stage_agent_dispatch_outbox(snapshot, request_ref)
            revision_cursor = commit_snapshot(
                resolved,
                snapshot,
                expected_revision=expected_revision if expected_revision is not None else revision_cursor,
                bump=True,
            )
            envelope = dispatch_for_agent_wait(snapshot, adapter=agent_adapter)
            revision_cursor = commit_snapshot(
                resolved,
                snapshot,
                expected_revision=revision_cursor,
                bump=True,
            )
            accept_outcome = try_accept_agent_envelope(
                snapshot,
                envelope,
                foundry_bundle=bundle,
            )
            if accept_outcome and accept_outcome.get("ok") and snapshot.get("wait") is None:
                steps_taken = int(advance_result.get("steps_taken") or 0)
                remaining = max(0, step_budget - steps_taken)
                if remaining > 0:
                    follow_up = advance_run(
                        snapshot,
                        flow,
                        workspace=workspace,
                        foundry_bundle=bundle,
                        run_dir=resolved,
                        step_budget=remaining,
                    )
                    advance_result = {
                        **advance_result,
                        "steps_taken": steps_taken + int(follow_up.get("steps_taken") or 0),
                        "reason": follow_up.get("reason", advance_result.get("reason")),
                        "status": follow_up.get("status", advance_result.get("status")),
                        "wait": follow_up.get("wait", advance_result.get("wait")),
                        "active_visit": follow_up.get("active_visit", advance_result.get("active_visit")),
                        "events_after": (advance_result.get("events_after") or [])
                        + (follow_up.get("events_after") or []),
                        "mutated": bool(advance_result.get("mutated"))
                        or bool(follow_up.get("mutated")),
                    }
            elif accept_outcome and accept_outcome.get("ok"):
                advance_result = {
                    **advance_result,
                    "wait": snapshot.get("wait"),
                }
        mutated = advance_result.get("mutated") or len(ledger_events(snapshot)) > ledger_before
        revision_after = revision_cursor
        if mutated:
            revision_after = commit_snapshot(
                resolved,
                snapshot,
                expected_revision=revision_cursor,
                bump=True,
            )
    except RunStoreError as exc:
        if exc.code == "STALE_REVISION":
            try:
                current = get_revision(load_snapshot(resolved))
            except RunStoreError:
                current = None
            return error(exc.code, exc.message, revision=current)
        return error(exc.code, exc.message)
    except ValueError as exc:
        return error("INVALID_FLOW", str(exc))

    active = advance_result.get("active_visit") or {}
    return ok(
        run_id=snapshot.get("run_id"),
        revision=revision_after,
        status=advance_result.get("status"),
        wait=advance_result.get("wait"),
        reason=advance_result.get("reason"),
        steps_taken=advance_result.get("steps_taken"),
        active_visit_id=active.get("id"),
        active_node_id=active.get("node_id"),
        active_lifecycle=active.get("lifecycle"),
        events_after_count=len(advance_result.get("events_after") or []),
    )


def recover_nonterminal_runs(workspace: Path, bundle: Path) -> list[dict[str, Any]]:
    """Advance each non-terminal run once (host startup recovery)."""
    runs_root = workspace / ".foundry" / "runs"
    if not runs_root.is_dir():
        return []
    outcomes: list[dict[str, Any]] = []
    for child in sorted(runs_root.iterdir()):
        if not child.is_dir() or not (child / "snapshot.json").is_file():
            continue
        try:
            snapshot = load_snapshot(child)
        except RunStoreError:
            continue
        status = str(snapshot.get("status") or "")
        if status in TERMINAL_RUN_STATUSES:
            continue
        result = advance_run_durable(
            workspace=workspace,
            bundle=bundle,
            run_dir=child,
            expected_revision=None,
        )
        outcomes.append(
            {
                "run_id": snapshot.get("run_id") or child.name,
                "ok": bool(result.get("ok")),
                "revision": result.get("revision"),
                "status": result.get("status"),
                "recovered": True,
            }
        )
    return outcomes


def submit_agent_result_durable(
    *,
    workspace: Path,
    bundle: Path,
    request_id: str,
    result: dict[str, Any],
    run_id: str | None = None,
    run_dir: Path | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)

    try:
        snapshot = load_snapshot(resolved)
        revision_before = get_revision(snapshot)
        if expected_revision is not None and revision_before != expected_revision:
            return error(
                "STALE_REVISION",
                f"Expected revision {expected_revision}, found {revision_before}",
                revision=revision_before,
            )
        outcome = submit_agent_result(
            snapshot,
            request_id=request_id,
            result=result,
            foundry_bundle=bundle,
        )
        if not outcome.get("ok"):
            return error(
                str(outcome.get("code") or "SUBMIT_FAILED"),
                str(outcome.get("message") or "Agent submit failed"),
                **{k: v for k, v in outcome.items() if k not in {"ok", "code", "message"}},
            )
        revision_after = commit_snapshot(
            resolved,
            snapshot,
            expected_revision=expected_revision,
            bump=True,
        )
    except RunStoreError as exc:
        if exc.code == "STALE_REVISION":
            try:
                current = get_revision(load_snapshot(resolved))
            except RunStoreError:
                current = None
            return error(exc.code, exc.message, revision=current)
        return error(exc.code, exc.message)

    return ok(
        run_id=snapshot.get("run_id"),
        revision=revision_after,
        request_id=request_id,
        wait=snapshot.get("wait"),
        open_clarifying_questions_count=outcome.get("open_clarifying_questions_count"),
        idempotent=bool(outcome.get("idempotent")),
    )


def answer_run_durable(
    *,
    workspace: Path,
    bundle: Path,
    answers: dict[str, str],
    run_id: str | None = None,
    run_dir: Path | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    """Submit clarifying answers when the active wait is user_input."""
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)

    try:
        snapshot = load_snapshot(resolved)
        revision_before = get_revision(snapshot)
        if expected_revision is not None and revision_before != expected_revision:
            return error(
                "STALE_REVISION",
                f"Expected revision {expected_revision}, found {revision_before}",
                revision=revision_before,
            )
        outcome = submit_clarifying_answers(snapshot, answers)
        if not outcome.get("ok"):
            return error(
                str(outcome.get("code") or "ANSWER_FAILED"),
                str(outcome.get("message") or "Answer submit failed"),
                **{k: v for k, v in outcome.items() if k not in {"ok", "code", "message"}},
            )
        revision_cursor = commit_snapshot(
            resolved,
            snapshot,
            expected_revision=expected_revision,
            bump=True,
        )
        revision_after = revision_cursor
        if snapshot.get("wait") is None:
            flow_id = str(snapshot.get("flow_id") or DEFAULT_FLOW_ID)
            _, flow = load_registry(bundle, flow_id=flow_id)
            advance_run(
                snapshot,
                flow,
                workspace=workspace,
                foundry_bundle=bundle,
                run_dir=resolved,
            )
            revision_after = commit_snapshot(
                resolved,
                snapshot,
                expected_revision=revision_cursor,
                bump=True,
            )
    except RunStoreError as exc:
        if exc.code == "STALE_REVISION":
            try:
                current = get_revision(load_snapshot(resolved))
            except RunStoreError:
                current = None
            return error(exc.code, exc.message, revision=current)
        return error(exc.code, exc.message)

    return ok(
        run_id=snapshot.get("run_id"),
        revision=revision_after,
        answers=answers,
        wait=snapshot.get("wait"),
        open_clarifying_questions_count=outcome.get("open_clarifying_questions_count"),
        active_node_id=(snapshot.get("active_visit") or {}).get("node_id")
        if isinstance(snapshot.get("active_visit"), dict)
        else None,
    )


def decide_run_durable(
    *,
    workspace: Path,
    bundle: Path,
    decision: str,
    run_id: str | None = None,
    run_dir: Path | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    """Record a user gate decision when the active wait is decision."""
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)

    try:
        snapshot = load_snapshot(resolved)
        revision_before = get_revision(snapshot)
        if expected_revision is not None and revision_before != expected_revision:
            return error(
                "STALE_REVISION",
                f"Expected revision {expected_revision}, found {revision_before}",
                revision=revision_before,
            )
        wait = snapshot.get("wait")
        if not isinstance(wait, dict):
            return error(
                "WAIT_KIND_MISMATCH",
                "Run is not waiting for user input",
                revision=revision_before,
                wait_kind=None,
            )
        wait_kind = str(wait.get("kind") or "")
        if wait_kind != "decision":
            return error(
                "WAIT_KIND_MISMATCH",
                f"Active wait is {wait_kind!r}; use the command matching that wait kind",
                revision=revision_before,
                wait_kind=wait_kind,
                wait=wait,
            )
        visit_id = str(wait.get("visit_id") or "")
        visit = _find_visit(snapshot, visit_id) if visit_id else None
        if visit is None:
            active = snapshot.get("active_visit")
            visit = active if isinstance(active, dict) else None
        if visit is None:
            return error("VISIT_NOT_FOUND", f"No visit for wait visit_id {visit_id!r}")

        flow_id = str(snapshot.get("flow_id") or DEFAULT_FLOW_ID)
        _, flow = load_registry(bundle, flow_id=flow_id)
        result = decide_gate(
            snapshot,
            visit,
            flow,
            decision=str(decision),
            workspace=workspace,
            foundry_bundle=bundle,
            run_dir=resolved,
        )
        if not result.get("ok"):
            return from_engine_result(result)
        clear_run_wait(snapshot)
        revision_after = commit_snapshot(
            resolved,
            snapshot,
            expected_revision=expected_revision,
            bump=True,
        )
    except RunStoreError as exc:
        if exc.code == "STALE_REVISION":
            try:
                current = get_revision(load_snapshot(resolved))
            except RunStoreError:
                current = None
            return error(exc.code, exc.message, revision=current)
        return error(exc.code, exc.message)
    except ValueError as exc:
        return error("INVALID_FLOW", str(exc))

    return ok(
        run_id=snapshot.get("run_id"),
        revision=revision_after,
        decision=decision,
        wait=snapshot.get("wait"),
        active_visit_id=visit.get("id"),
        active_node_id=visit.get("node_id"),
        next_node_id=result.get("next_node_id"),
        next_lifecycle=result.get("next_lifecycle"),
    )


def _active_visit_for_mutation(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    active = snapshot.get("active_visit")
    if isinstance(active, dict):
        return active
    return None


def execute_start_durable(
    *,
    workspace: Path,
    bundle: Path,
    run_id: str | None = None,
    run_dir: Path | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    """Explicit Shape → Execute authorization at execute.start."""
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)

    try:
        snapshot = load_snapshot(resolved)
        revision_before = get_revision(snapshot)
        if expected_revision is not None and revision_before != expected_revision:
            return error(
                "STALE_REVISION",
                f"Expected revision {expected_revision}, found {revision_before}",
                revision=revision_before,
            )
        visit = _active_visit_for_mutation(snapshot)
        if visit is None:
            return error("VISIT_NOT_FOUND", "No active visit on run")

        flow_id = str(snapshot.get("flow_id") or DEFAULT_FLOW_ID)
        _, flow = load_registry(bundle, flow_id=flow_id)
        result = execute_start_authorization(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=bundle,
            run_dir=resolved,
        )
        if not result.get("ok"):
            return from_engine_result(result)
        revision_after = commit_snapshot(
            resolved,
            snapshot,
            expected_revision=expected_revision,
            bump=True,
        )
    except RunStoreError as exc:
        if exc.code == "STALE_REVISION":
            try:
                current = get_revision(load_snapshot(resolved))
            except RunStoreError:
                current = None
            return error(exc.code, exc.message, revision=current)
        return error(exc.code, exc.message)
    except ValueError as exc:
        return error("INVALID_FLOW", str(exc))

    active = snapshot.get("active_visit") if isinstance(snapshot.get("active_visit"), dict) else {}
    return ok(
        run_id=snapshot.get("run_id"),
        revision=revision_after,
        authorization_recorded=True,
        decision=result.get("decision"),
        next_node_id=result.get("next_node_id"),
        next_lifecycle=result.get("next_lifecycle"),
        active_visit_id=active.get("id"),
        active_node_id=active.get("node_id"),
        status=snapshot.get("status"),
        wait=snapshot.get("wait"),
    )


def retry_run_durable(
    *,
    workspace: Path,
    bundle: Path,
    run_id: str | None = None,
    run_dir: Path | None = None,
    expected_revision: int | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)

    try:
        snapshot = load_snapshot(resolved)
        revision_before = get_revision(snapshot)
        if expected_revision is not None and revision_before != expected_revision:
            return error(
                "STALE_REVISION",
                f"Expected revision {expected_revision}, found {revision_before}",
                revision=revision_before,
            )
        outcome = retry_run(snapshot, reason=reason)
        if not outcome.get("ok"):
            return from_engine_result(outcome)
        revision_after = commit_snapshot(
            resolved,
            snapshot,
            expected_revision=expected_revision,
            bump=True,
        )
    except RunStoreError as exc:
        if exc.code == "STALE_REVISION":
            try:
                current = get_revision(load_snapshot(resolved))
            except RunStoreError:
                current = None
            return error(exc.code, exc.message, revision=current)
        return error(exc.code, exc.message)

    active = snapshot.get("active_visit") if isinstance(snapshot.get("active_visit"), dict) else {}
    return ok(
        run_id=snapshot.get("run_id"),
        revision=revision_after,
        status=snapshot.get("status"),
        prior_status=outcome.get("prior_status"),
        wait=snapshot.get("wait"),
        active_node_id=active.get("node_id"),
    )


def cancel_run_durable(
    *,
    workspace: Path,
    bundle: Path,
    reason: str,
    run_id: str | None = None,
    run_dir: Path | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)

    try:
        snapshot = load_snapshot(resolved)
        revision_before = get_revision(snapshot)
        if expected_revision is not None and revision_before != expected_revision:
            return error(
                "STALE_REVISION",
                f"Expected revision {expected_revision}, found {revision_before}",
                revision=revision_before,
            )
        outcome = cancel_run(snapshot, reason=reason)
        if not outcome.get("ok"):
            return from_engine_result(outcome)
        revision_after = commit_snapshot(
            resolved,
            snapshot,
            expected_revision=expected_revision,
            bump=True,
        )
    except RunStoreError as exc:
        if exc.code == "STALE_REVISION":
            try:
                current = get_revision(load_snapshot(resolved))
            except RunStoreError:
                current = None
            return error(exc.code, exc.message, revision=current)
        return error(exc.code, exc.message)

    return ok(
        run_id=snapshot.get("run_id"),
        revision=revision_after,
        status=outcome.get("status"),
        prior_status=outcome.get("prior_status"),
        reason=outcome.get("reason"),
        wait=snapshot.get("wait"),
    )
