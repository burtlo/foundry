"""User-facing Shape CLI commands (Phase 5)."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from foundry_cli.command_context import CommandContext
from foundry_cli.engine.advance import TERMINAL_RUN_STATUSES
from foundry_cli.engine.blocked_intake import BLOCKED_INTAKE_STATUS_CODE
from foundry_cli.engine.intake_executor import BLOCK_REASON_MISSING_WORK_PROMPT
from foundry_cli.errors import error, ok
from foundry_cli.host.client import call_host
from foundry_cli.host.discovery import host_is_running
from foundry_cli.run_labels import phase_label
from foundry_cli.run_service import (
    advance_run_durable,
    answer_run_durable,
    cancel_run_durable,
    create_run,
    decide_run_durable,
    execute_start_durable,
    get_run,
    list_runs,
    retry_run_durable,
    run_events,
)
from foundry_cli.run_store import load_snapshot, resolve_run_dir, RunStoreError


def _parse_expected_revision(args: argparse.Namespace) -> int | None:
    raw = getattr(args, "revision", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return -1


def _resolve_shape_input(args: argparse.Namespace) -> dict[str, Any] | str:
    inline = getattr(args, "input", None)
    path = getattr(args, "input_file", None)
    if inline and path:
        return error("INVALID_FLAGS", "Use only one of --input (--prompt) or --input-file")
    if inline:
        text = str(inline)
        if not text.strip():
            return error(
                "INPUT_REQUIRED",
                "Shape request is empty; provide non-empty text via --input or --prompt",
            )
        return text
    if path:
        file_path = Path(path).resolve()
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            return error("INPUT_READ_FAILED", f"Could not read --input-file: {exc}")
        if not text.strip():
            return error(
                "INPUT_REQUIRED",
                "Shape input file is empty; add a work request or use --input/--prompt",
            )
        return text
    return error(
        "INPUT_REQUIRED",
        "Provide a shape request via --input, --prompt, or --input-file",
    )


def _shape_intake_blocked_error(
    advance_result: dict[str, Any],
    *,
    run_id: str,
) -> dict[str, Any] | None:
    """Map engine blocked intake to a CLI failure envelope."""
    reason = advance_result.get("reason")
    detail = advance_result.get("detail")
    detail_dict = detail if isinstance(detail, dict) else {}

    intake_status = advance_result.get("intake_status")
    if intake_status is None:
        intake_status = detail_dict.get("intake_status")

    if reason != "intake_blocked" and intake_status != "blocked":
        return None

    block_reason = detail_dict.get("block_reason")
    if block_reason == BLOCK_REASON_MISSING_WORK_PROMPT:
        message = "Shape intake blocked: work request missing or insufficient."
    elif block_reason:
        message = f"Shape intake blocked ({block_reason})."
    else:
        message = "Shape intake blocked."

    return error(
        BLOCKED_INTAKE_STATUS_CODE,
        message,
        run_id=run_id,
        intake_status="blocked",
        block_reason=block_reason,
        reason=reason,
    )


def _ensure_host(ctx: CommandContext, args: argparse.Namespace) -> dict[str, Any] | None:
    if getattr(args, "no_host", False):
        return None
    from foundry_cli.readiness.preflight import preflight_check

    pf = preflight_check(ctx.workspace)
    if not pf.get("ok"):
        return pf
    return None


SHAPE_INTAKE_STOP_REASON = "intake_complete"


def _advance_via_host_or_local(
    ctx: CommandContext,
    args: argparse.Namespace,
    *,
    run_id: str,
    expected_revision: int,
    step_budget: int = 8,
    stop_after_advance_reason: str | None = None,
) -> dict[str, Any]:
    advance_params: dict[str, Any] = {
        "run_id": run_id,
        "expected_revision": expected_revision,
        "step_budget": step_budget,
        "idempotency_key": str(uuid.uuid4()),
    }
    if stop_after_advance_reason:
        advance_params["stop_after_advance_reason"] = stop_after_advance_reason
    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        return call_host(ctx.workspace, "run.advance", advance_params)
    return advance_run_durable(
        workspace=ctx.workspace,
        bundle=ctx.bundle,
        run_id=run_id,
        expected_revision=expected_revision,
        flow_id=getattr(args, "flow", None),
        step_budget=step_budget,
        stop_after_advance_reason=stop_after_advance_reason,
    )


def _resolve_run_id(
    workspace: Path,
    run_id: str | None,
    *,
    local: bool = False,
) -> dict[str, Any]:
    if run_id:
        return ok(run_id=run_id)
    listed = list_runs(workspace) if local or not host_is_running(workspace) else call_host(
        workspace, "run.list", {}
    )
    if not listed.get("ok"):
        return listed
    runs = listed.get("runs") or []
    active = [
        r
        for r in runs
        if isinstance(r, dict) and str(r.get("status") or "") not in TERMINAL_RUN_STATUSES
    ]
    if not active:
        return error("RUN_NOT_FOUND", "No active runs in workspace; pass an explicit run id")
    if len(active) > 1:
        ids = ", ".join(str(r.get("run_id")) for r in active[:5])
        return error(
            "AMBIGUOUS_RUN",
            f"Multiple active runs ({ids}); pass run id explicitly",
            runs=active,
        )
    return ok(run_id=str(active[0].get("run_id")))


def cmd_shape(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    resolved_input = _resolve_shape_input(args)
    if isinstance(resolved_input, dict):
        return resolved_input
    work_prompt: str = resolved_input

    host_err = _ensure_host(ctx, args)
    if host_err is not None:
        return host_err

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        create_result = call_host(
            ctx.workspace,
            "run.create",
            {
                "work_prompt": work_prompt,
                "flow_id": getattr(args, "flow", None),
                "run_id": getattr(args, "run_id", None),
                "idempotency_key": str(uuid.uuid4()),
            },
        )
    else:
        create_result = create_run(
            workspace=ctx.workspace,
            bundle=ctx.bundle,
            work_prompt=work_prompt,
            flow_id=getattr(args, "flow", None),
            run_id=getattr(args, "run_id", None),
        )

    if not create_result.get("ok"):
        return create_result

    run_id = str(create_result.get("run_id"))
    revision = int(create_result.get("revision") or 1)

    try:
        run_dir = resolve_run_dir(run_id=run_id, run_dir=None, workspace=ctx.workspace)
        snapshot = load_snapshot(run_dir)
        config = snapshot.get("config") if isinstance(snapshot.get("config"), dict) else {}
        shape_cfg = config.get("shape") if isinstance(config.get("shape"), dict) else {}
        stored = shape_cfg.get("work_prompt")
        if stored != work_prompt:
            return error(
                "WORK_PROMPT_NOT_PERSISTED",
                "Shape request was not durably stored before advance",
            )
    except RunStoreError as exc:
        return error(exc.code, exc.message)

    advance_result = _advance_via_host_or_local(
        ctx,
        args,
        run_id=run_id,
        expected_revision=revision,
        step_budget=8,
        stop_after_advance_reason=SHAPE_INTAKE_STOP_REASON,
    )
    if not advance_result.get("ok"):
        return advance_result

    blocked = _shape_intake_blocked_error(advance_result, run_id=run_id)
    if blocked is not None:
        return blocked

    intake_status = advance_result.get("intake_status")
    if intake_status is None:
        detail = advance_result.get("detail")
        if isinstance(detail, dict):
            intake_status = detail.get("intake_status")

    return ok(
        run_id=run_id,
        work_prompt=work_prompt,
        revision=advance_result.get("revision"),
        status=advance_result.get("status"),
        wait=advance_result.get("wait"),
        reason=advance_result.get("reason"),
        active_node_id=advance_result.get("active_node_id"),
        active_visit_id=advance_result.get("active_visit_id"),
        run_dir=create_result.get("run_dir"),
        intake_status=intake_status,
        intake_complete=advance_result.get("reason") == SHAPE_INTAKE_STOP_REASON,
        attach_hint=f"foundry attach {run_id}",
        status_hint=f"foundry status {run_id}",
    )


def cmd_runs(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        return call_host(ctx.workspace, "run.list", {})
    return list_runs(ctx.workspace)


def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    run_id = getattr(args, "run", None)
    if not run_id:
        resolved = _resolve_run_id(
            ctx.workspace,
            None,
            local=getattr(args, "local", False),
        )
        if not resolved.get("ok"):
            return resolved
        run_id = str(resolved.get("run_id"))

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        result = call_host(ctx.workspace, "run.get", {"run_id": run_id})
    else:
        result = get_run(ctx.workspace, run_id=run_id, bundle=ctx.bundle)

    if not result.get("ok"):
        return result

    wait = result.get("wait")
    wait_kind = wait.get("kind") if isinstance(wait, dict) else None
    return ok(
        run_id=result.get("run_id"),
        revision=result.get("revision"),
        status=result.get("status"),
        active_node_id=result.get("active_node_id"),
        active_visit_id=result.get("active_visit_id"),
        active_lifecycle=result.get("active_lifecycle"),
        wait=wait,
        wait_kind=wait_kind,
        handoff_message=result.get("handoff_message"),
        run_dir=result.get("run_dir"),
        halt_reason=result.get("halt_reason"),
        status_reason=result.get("status_reason"),
        phase=phase_label(str(result.get("active_node_id") or "")),
        parked=result.get("parked"),
    )


def _expected_revision_for_run(
    ctx: CommandContext,
    args: argparse.Namespace,
    run_id: str,
) -> int | dict[str, Any]:
    expected = _parse_expected_revision(args)
    if expected == -1:
        return error("INVALID_REVISION", "revision must be an integer")
    if expected is not None:
        return expected
    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        current = call_host(ctx.workspace, "run.get", {"run_id": run_id})
    else:
        current = get_run(ctx.workspace, run_id=run_id)
    if not current.get("ok"):
        return current
    return int(current.get("revision") or 0)


def _fetch_run_snapshot(
    ctx: CommandContext,
    args: argparse.Namespace,
    run_id: str,
) -> dict[str, Any]:
    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        return call_host(ctx.workspace, "run.get", {"run_id": run_id})
    return get_run(ctx.workspace, run_id=run_id)


def _load_run_snapshot_document(
    ctx: CommandContext,
    args: argparse.Namespace,
    run_id: str,
) -> dict[str, Any]:
    """Full run snapshot for attach streaming (includes state for clarifying questions)."""
    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        host_result = call_host(ctx.workspace, "run.get", {"run_id": run_id})
        if not host_result.get("ok"):
            return host_result
        if isinstance(host_result.get("state"), dict):
            return host_result
    try:
        run_dir = resolve_run_dir(run_id=run_id, run_dir=None, workspace=ctx.workspace)
        return load_snapshot(run_dir)
    except RunStoreError as exc:
        return error(exc.code, exc.message)


def _open_clarifying_questions(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    state = snapshot.get("state")
    if not isinstance(state, dict):
        return []
    questions = state.get("clarifying_questions")
    if not isinstance(questions, list):
        return []
    open_items: list[dict[str, Any]] = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "open") == "answered":
            continue
        open_items.append(item)
    return open_items


def _print_human_clarifying_questions(snapshot: dict[str, Any]) -> None:
    for item in _open_clarifying_questions(snapshot):
        qid = str(item.get("id") or "")
        text = str(item.get("text") or qid)
        print(f"question {qid}: {text}", file=sys.stderr)


def _print_ledger_follow_header(snapshot: dict[str, Any]) -> None:
    print(
        f"run={snapshot.get('run_id')} status={snapshot.get('status')} "
        f"node={snapshot.get('active_node_id')} revision={snapshot.get('revision')}",
        file=sys.stderr,
    )
    wait = snapshot.get("wait")
    if isinstance(wait, dict):
        print(
            f"wait kind={wait.get('kind')} summary={wait.get('summary')!r}",
            file=sys.stderr,
        )


_ATTACH_NOT_TTY = (
    "foundry attach requires an interactive terminal. "
    "Use `foundry ledger show --run RUN` (with `--json` for automation) for a snapshot and event batch, "
    "or `foundry ledger follow --run RUN` to stream JSON lines."
)


def stream_ledger_follow(
    ctx: CommandContext,
    args: argparse.Namespace,
    *,
    run_id: str,
    after_seq: int = 0,
    human_questions: bool = False,
) -> dict[str, Any]:
    """Follow ledger events for a run until interrupted (detach does not cancel the run)."""
    snapshot = _load_run_snapshot_document(ctx, args, run_id)
    if snapshot.get("ok") is False:
        return snapshot

    _print_ledger_follow_header(snapshot)
    if human_questions:
        wait = snapshot.get("wait")
        if isinstance(wait, dict) and wait.get("kind") == "user_input":
            _print_human_clarifying_questions(snapshot)

    cursor = after_seq
    printed_wait_id: str | None = None
    try:
        while True:
            if host_is_running(ctx.workspace) and not getattr(args, "local", False):
                batch = call_host(
                    ctx.workspace,
                    "run.events",
                    {"run_id": run_id, "after_seq": cursor},
                )
            else:
                batch = run_events(ctx.workspace, run_id=run_id, after_seq=cursor)
            if not batch.get("ok"):
                print(
                    f"error [{batch.get('error', {}).get('code')}]: "
                    f"{batch.get('error', {}).get('message')}",
                    file=sys.stderr,
                )
                return batch
            saw_events = False
            for event in batch.get("events") or []:
                if isinstance(event, dict):
                    print(json.dumps(event, sort_keys=True))
                    seq = event.get("seq")
                    if isinstance(seq, int):
                        cursor = max(cursor, seq)
                    saw_events = True
                    if human_questions and event.get("event_type") == "agent.result.accepted":
                        fresh = _load_run_snapshot_document(ctx, args, run_id)
                        if fresh.get("ok") is not False:
                            wait = fresh.get("wait")
                            if isinstance(wait, dict) and wait.get("kind") == "user_input":
                                wait_id = str(wait.get("id") or "")
                                if wait_id != printed_wait_id:
                                    _print_human_clarifying_questions(fresh)
                                    printed_wait_id = wait_id
            if human_questions and saw_events:
                fresh = _load_run_snapshot_document(ctx, args, run_id)
                if fresh.get("ok") is not False:
                    wait = fresh.get("wait")
                    if isinstance(wait, dict) and wait.get("kind") == "user_input":
                        wait_id = str(wait.get("id") or "")
                        if wait_id != printed_wait_id:
                            _print_human_clarifying_questions(fresh)
                            printed_wait_id = wait_id
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("detached (run continues)", file=sys.stderr)
        return ok(detached=True, run_id=run_id, after_seq=cursor)


def stream_run_attach(
    ctx: CommandContext,
    args: argparse.Namespace,
    *,
    run_id: str,
    after_seq: int = 0,
    human_questions: bool = False,
) -> dict[str, Any]:
    """Compatibility alias delegating to ledger follow (shape --attach uses interactive attach)."""
    return stream_ledger_follow(
        ctx,
        args,
        run_id=run_id,
        after_seq=after_seq,
        human_questions=human_questions,
    )


def cmd_ledger_follow(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    run_id = getattr(args, "run", None)
    if not run_id:
        return error("RUN_REQUIRED", "ledger follow requires --run")

    after_seq = int(getattr(args, "after_seq", None) or 0)
    return stream_ledger_follow(ctx, args, run_id=run_id, after_seq=after_seq)


def cmd_attach(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    run_id = getattr(args, "run", None)
    after_seq = int(getattr(args, "after_seq", None) or 0)
    no_follow = bool(getattr(args, "no_follow", False))
    use_json = bool(getattr(args, "json", False))

    if use_json or no_follow:
        if not run_id:
            return error("RUN_REQUIRED", "attach batch mode requires a run id")
    else:
        if not sys.stdout.isatty():
            return error("ATTACH_NOT_TTY", _ATTACH_NOT_TTY)
        try:
            from foundry_cli.tui import run_interactive_attach
        except ImportError as exc:
            return error(
                "TUI_DEPENDENCY_MISSING",
                "Textual is required for foundry attach. Install with: pip install textual",
                detail=str(exc),
            )
        registry = getattr(args, "registry", None)
        run_interactive_attach(
            workspace=ctx.workspace,
            registry=registry,
            run_id=run_id,
        )
        return ok(launched=True, run_id=run_id)

    snapshot = _fetch_run_snapshot(ctx, args, run_id)
    if not snapshot.get("ok"):
        return snapshot

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        events = call_host(
            ctx.workspace,
            "run.events",
            {"run_id": run_id, "after_seq": after_seq},
        )
    else:
        events = run_events(ctx.workspace, run_id=run_id, after_seq=after_seq)
    if not events.get("ok"):
        return events
    return ok(
        run_id=run_id,
        snapshot={
            k: snapshot.get(k)
            for k in (
                "run_id",
                "revision",
                "status",
                "wait",
                "active_node_id",
                "active_visit_id",
                "active_lifecycle",
                "run_dir",
            )
        },
        after_seq=after_seq,
        events=events.get("events") or [],
    )


def _parse_answers_arg(args: argparse.Namespace) -> dict[str, Any] | dict[str, str]:
    raw = getattr(args, "answers", None)
    if not raw:
        return error("ANSWERS_REQUIRED", "Usage: foundry answer RUN --answers '{\"q1\": \"...\"}'")
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError as exc:
        return error("INVALID_ANSWERS", f"--answers must be valid JSON: {exc}")
    if not isinstance(parsed, dict) or not parsed:
        return error("INVALID_ANSWERS", "--answers must be a non-empty JSON object")
    return {str(k): str(v) for k, v in parsed.items()}


def cmd_answer(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    run_id = getattr(args, "run", None)
    if not run_id:
        return error("INVALID_REQUEST", "Usage: foundry answer RUN --answers '{\"q1\": \"...\"}'")

    answers = _parse_answers_arg(args)
    if isinstance(answers, dict) and answers.get("ok") is False:
        return answers

    expected = _expected_revision_for_run(ctx, args, run_id)
    if isinstance(expected, dict):
        return expected

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        return call_host(
            ctx.workspace,
            "run.answer",
            {
                "run_id": run_id,
                "answers": answers,
                "expected_revision": expected,
                "idempotency_key": str(uuid.uuid4()),
            },
        )

    return answer_run_durable(
        workspace=ctx.workspace,
        bundle=ctx.bundle,
        run_id=run_id,
        answers=answers,
        expected_revision=expected,
    )


def cmd_decide(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    run_id = getattr(args, "run", None)
    option = getattr(args, "option", None)
    if not run_id or not option:
        return error("INVALID_REQUEST", "Usage: foundry decide RUN <option>")

    expected = _expected_revision_for_run(ctx, args, run_id)
    if isinstance(expected, dict):
        return expected

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        return call_host(
            ctx.workspace,
            "run.decide",
            {
                "run_id": run_id,
                "decision": str(option),
                "expected_revision": expected,
                "idempotency_key": str(uuid.uuid4()),
            },
        )

    return decide_run_durable(
        workspace=ctx.workspace,
        bundle=ctx.bundle,
        run_id=run_id,
        decision=str(option),
        expected_revision=expected,
    )


def cmd_start(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    run_id = getattr(args, "run", None)
    if not run_id:
        resolved = _resolve_run_id(
            ctx.workspace,
            None,
            local=getattr(args, "local", False),
        )
        if not resolved.get("ok"):
            return resolved
        run_id = str(resolved.get("run_id"))

    host_err = _ensure_host(ctx, args)
    if host_err is not None:
        return host_err

    expected = _expected_revision_for_run(ctx, args, run_id)
    if isinstance(expected, dict):
        return expected

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        start_result = call_host(
            ctx.workspace,
            "run.start",
            {
                "run_id": run_id,
                "expected_revision": expected,
                "idempotency_key": str(uuid.uuid4()),
            },
        )
    else:
        start_result = execute_start_durable(
            workspace=ctx.workspace,
            bundle=ctx.bundle,
            run_id=run_id,
            expected_revision=expected,
        )

    if not start_result.get("ok"):
        return start_result

    revision = int(start_result.get("revision") or expected)
    advance_result = _advance_via_host_or_local(
        ctx,
        args,
        run_id=run_id,
        expected_revision=revision,
    )
    if not advance_result.get("ok"):
        return advance_result

    return ok(
        run_id=run_id,
        revision=advance_result.get("revision"),
        authorization_recorded=True,
        status=advance_result.get("status"),
        wait=advance_result.get("wait"),
        active_node_id=advance_result.get("active_node_id"),
        active_visit_id=advance_result.get("active_visit_id"),
        next_node_id=start_result.get("next_node_id"),
        phase=phase_label(str(advance_result.get("active_node_id") or "")),
    )


def cmd_retry(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    run_id = getattr(args, "run", None)
    if not run_id:
        return error("RUN_REQUIRED", "retry requires a run id")

    reason = getattr(args, "reason", None)
    expected = _expected_revision_for_run(ctx, args, run_id)
    if isinstance(expected, dict):
        return expected

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        retry_result = call_host(
            ctx.workspace,
            "run.retry",
            {
                "run_id": run_id,
                "expected_revision": expected,
                "idempotency_key": str(uuid.uuid4()),
                "reason": reason,
            },
        )
    else:
        retry_result = retry_run_durable(
            workspace=ctx.workspace,
            bundle=ctx.bundle,
            run_id=run_id,
            expected_revision=expected,
            reason=reason,
        )

    if not retry_result.get("ok"):
        return retry_result

    revision = int(retry_result.get("revision") or expected)
    advance_result = _advance_via_host_or_local(
        ctx,
        args,
        run_id=run_id,
        expected_revision=revision,
        step_budget=4,
    )
    if not advance_result.get("ok"):
        return advance_result

    return ok(
        run_id=run_id,
        revision=advance_result.get("revision"),
        status=advance_result.get("status"),
        wait=advance_result.get("wait"),
        active_node_id=advance_result.get("active_node_id"),
        prior_status=retry_result.get("prior_status"),
        phase=phase_label(str(advance_result.get("active_node_id") or "")),
    )


def cmd_cancel(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    run_id = getattr(args, "run", None)
    if not run_id:
        return error("RUN_REQUIRED", "cancel requires a run id")

    reason = getattr(args, "reason", None)
    if not reason or not str(reason).strip():
        return error("REASON_REQUIRED", "cancel requires --reason")

    expected = _expected_revision_for_run(ctx, args, run_id)
    if isinstance(expected, dict):
        return expected

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        return call_host(
            ctx.workspace,
            "run.cancel",
            {
                "run_id": run_id,
                "expected_revision": expected,
                "idempotency_key": str(uuid.uuid4()),
                "reason": str(reason).strip(),
            },
        )

    return cancel_run_durable(
        workspace=ctx.workspace,
        bundle=ctx.bundle,
        run_id=run_id,
        expected_revision=expected,
        reason=str(reason).strip(),
    )
