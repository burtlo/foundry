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
from foundry_cli.errors import error, ok
from foundry_cli.host.client import call_host
from foundry_cli.host.discovery import host_is_running
from foundry_cli.host_commands import cmd_host_start
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
        return error("INVALID_FLAGS", "Use only one of --input or --input-file")
    if inline:
        text = str(inline).strip()
        if not text:
            return error("INPUT_REQUIRED", "--input must not be empty")
        return text
    if path:
        file_path = Path(path).resolve()
        try:
            text = file_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            return error("INPUT_READ_FAILED", f"Could not read --input-file: {exc}")
        if not text:
            return error("INPUT_REQUIRED", "Input file is empty")
        return text
    return error("INPUT_REQUIRED", "Provide --input or --input-file")


def _ensure_host(ctx: CommandContext, args: argparse.Namespace) -> dict[str, Any] | None:
    if host_is_running(ctx.workspace):
        return None
    if getattr(args, "no_host", False):
        return None
    started = cmd_host_start(args)
    if not started.get("ok"):
        return started
    return None


def _advance_via_host_or_local(
    ctx: CommandContext,
    args: argparse.Namespace,
    *,
    run_id: str,
    expected_revision: int,
    step_budget: int = 8,
) -> dict[str, Any]:
    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        return call_host(
            ctx.workspace,
            "run.advance",
            {
                "run_id": run_id,
                "expected_revision": expected_revision,
                "step_budget": step_budget,
                "idempotency_key": str(uuid.uuid4()),
            },
        )
    return advance_run_durable(
        workspace=ctx.workspace,
        bundle=ctx.bundle,
        run_id=run_id,
        expected_revision=expected_revision,
        flow_id=getattr(args, "flow", None),
        step_budget=step_budget,
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
    )
    if not advance_result.get("ok"):
        return advance_result

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
        result = get_run(ctx.workspace, run_id=run_id)

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
        run_dir=result.get("run_dir"),
        phase=_phase_label(str(result.get("active_node_id") or "")),
    )


def _phase_label(node_id: str) -> str:
    if node_id.startswith("shape."):
        return "shape"
    if node_id.startswith("execute."):
        return "execute"
    if node_id.startswith("implement."):
        return "implement"
    if node_id.startswith("verify."):
        return "verify"
    return "unknown"


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


def cmd_attach(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    run_id = getattr(args, "run", None)
    if not run_id:
        return error("RUN_REQUIRED", "attach requires a run id")

    after_seq = int(getattr(args, "after_seq", None) or 0)
    no_follow = bool(getattr(args, "no_follow", False))
    use_json = bool(getattr(args, "json", False))
    stream = not use_json and not no_follow

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        snapshot = call_host(ctx.workspace, "run.get", {"run_id": run_id})
    else:
        snapshot = get_run(ctx.workspace, run_id=run_id)

    if not snapshot.get("ok"):
        return snapshot

    if not stream:
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

    cursor = after_seq
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
            for event in batch.get("events") or []:
                if isinstance(event, dict):
                    print(json.dumps(event, sort_keys=True))
                    seq = event.get("seq")
                    if isinstance(seq, int):
                        cursor = max(cursor, seq)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("detached (run continues)", file=sys.stderr)
        return ok(detached=True, run_id=run_id, after_seq=cursor)


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
        phase=_phase_label(str(advance_result.get("active_node_id") or "")),
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
        phase=_phase_label(str(advance_result.get("active_node_id") or "")),
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
