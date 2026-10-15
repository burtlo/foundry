"""CLI commands for the local Foundry job host."""

from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from foundry_cli.command_context import CommandContext
from foundry_cli.errors import error, ok
from foundry_cli.host.client import call_host, host_status_payload
from foundry_cli.host.discovery import clear_state, host_is_running, host_startup_lock, pid_alive, read_state
from foundry_cli.host.auto_advance_status import read_auto_advance_status
from foundry_cli.host.log_reader import (
    append_host_start_marker,
    follow_log,
    read_log_since_marker,
    read_log_tail,
)
from foundry_cli.host.paths import host_log_path, startup_log_path
from foundry_cli.host.server import run_host_process
from foundry_cli.readiness.preflight import preflight_check
from foundry_cli.spawn_env import child_process_env
from foundry_cli.util import now_iso

DEFAULT_AUTO_ADVANCE_INTERVAL = 2.0


def configure_host_start_for_up(args: argparse.Namespace) -> None:
    """Enable host auto-advance when ``foundry up`` starts or restarts the host."""
    setattr(args, "auto_advance", True)
    if getattr(args, "auto_advance_interval", None) is None:
        setattr(args, "auto_advance_interval", DEFAULT_AUTO_ADVANCE_INTERVAL)


def _spawn_detached(
    argv: list[str],
    *,
    cwd: Path,
    workspace: Path,
    bundle: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen[Any]:
    log_path = host_log_path(workspace.resolve())
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("a", encoding="utf-8")
    env: dict[str, str] | None = None
    if bundle is not None:
        env = child_process_env(bundle, extra=extra_env)
    elif extra_env:
        import os

        env = {**os.environ, **extra_env}
    kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": log_handle,
    }
    if env is not None:
        kwargs["env"] = env
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(argv, **kwargs)


def cmd_host_start(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    spawn_extra = getattr(args, "_host_spawn_env", None)
    if not isinstance(spawn_extra, dict):
        spawn_extra = {}
    expected_bridge = spawn_extra.get("FOUNDRY_AGENT_HTTP_URL")
    if not getattr(args, "skip_preflight", False) and not host_is_running(ctx.workspace):
        pf = preflight_check(
            ctx.workspace,
            expected_bridge_url=expected_bridge,
            require_host=False,
        )
        if not pf.get("ok"):
            return pf
    start_id = str(uuid.uuid4())
    start_marker_at = now_iso()

    if host_is_running(ctx.workspace):
        status = host_status_payload(ctx.workspace)
        return ok(already_running=True, **{k: v for k, v in status.items() if k != "ok"})

    try:
        with host_startup_lock(ctx.workspace):
            if host_is_running(ctx.workspace):
                return ok(already_running=True, running=True)
            argv = [
                sys.executable,
                "-m",
                "foundry_cli.host",
                "--workspace",
                str(ctx.workspace),
            ]
            if args.registry:
                argv.extend(["--registry", str(Path(args.registry).resolve())])
            if getattr(args, "auto_advance", False):
                argv.append("--auto-advance")
                interval = getattr(args, "auto_advance_interval", None)
                if interval is not None:
                    argv.extend(["--auto-advance-interval", str(float(interval))])
            proc = _spawn_detached(
                argv,
                cwd=ctx.workspace,
                workspace=ctx.workspace,
                bundle=ctx.bundle,
                extra_env=spawn_extra or None,
            )
    except OSError as exc:
        return error("HOST_START_FAILED", str(exc))

    for _ in range(50):
        if host_is_running(ctx.workspace):
            state = read_state(ctx.workspace)
            from foundry_cli.host.discovery import write_state

            if state:
                auto_adv = (
                    bool(state["auto_advance"])
                    if "auto_advance" in state
                    else bool(getattr(args, "auto_advance", False))
                )
                interval = state.get("auto_advance_interval")
                if interval is None:
                    interval = getattr(args, "auto_advance_interval", None)
                write_state(
                    ctx.workspace,
                    pid=int(state.get("pid") or proc.pid),
                    transport=str(state.get("transport") or "tcp"),
                    address=str(state.get("address") or ""),
                    port=int(state.get("port") or 0) if state.get("port") is not None else None,
                    auto_advance=auto_adv,
                    auto_advance_interval=interval,
                    agent_adapter=spawn_extra.get("FOUNDRY_AGENT_ADAPTER"),
                    agent_http_url=spawn_extra.get("FOUNDRY_AGENT_HTTP_URL"),
                    start_id=start_id,
                    start_marker_at=start_marker_at,
                )
                append_host_start_marker(
                    host_log_path(ctx.workspace.resolve()),
                    start_id,
                    start_marker_at,
                )
            return ok(
                started=True,
                auto_advance=bool(getattr(args, "auto_advance", False)),
                pid=state.get("pid") if state else proc.pid,
                transport=state.get("transport") if state else None,
                address=state.get("address") if state else None,
                start_id=start_id,
            )
        import time

        time.sleep(0.1)

    message = "Host process did not publish discovery state in time"
    log = startup_log_path(ctx.workspace)
    if log.is_file():
        tail = log.read_text(encoding="utf-8").strip()
        if tail:
            message = f"{message}. Startup log: {tail[-500:]}"
    return error("HOST_START_FAILED", message)


def cmd_host_status(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args, require_registry=False)
    if isinstance(ctx, dict):
        return ctx
    return host_status_payload(ctx.workspace)


def _resolve_log_path(workspace: Path, source: str) -> Path:
    if source == "startup":
        return startup_log_path(workspace)
    if source == "host":
        return host_log_path(workspace)
    raise ValueError(f"unknown log source: {source!r}")


def cmd_host_logs(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args, require_registry=False)
    if isinstance(ctx, dict):
        return ctx

    source = str(getattr(args, "source", None) or "host")
    if source not in {"host", "startup"}:
        return error("INVALID_FLAGS", "--source must be 'host' or 'startup'")

    workspace = ctx.workspace.resolve()
    path = _resolve_log_path(workspace, source)
    lines_n = int(getattr(args, "lines", None) or 200)
    follow = bool(getattr(args, "follow", False))
    use_json = bool(getattr(args, "json", False))
    since_start = bool(getattr(args, "since_start", False))

    if follow and use_json:
        return error("INVALID_FLAGS", "--follow cannot be used with --json")

    state = read_state(workspace)
    pid = int(state.get("pid") or 0) if state else None
    marker_at = state.get("start_marker_at") if state else None
    start_id = state.get("start_id") if state else None
    scope_to_start = bool(marker_at or start_id) or since_start

    if follow:
        print(f"log={path} pid={pid} read_at={now_iso()}")
        try:
            if scope_to_start and (marker_at or start_id):
                follow_log(
                    path,
                    max_lines=lines_n,
                    marker_timestamp=str(marker_at) if marker_at else None,
                    start_id=str(start_id) if start_id else None,
                )
            else:
                follow_log(path, max_lines=lines_n)
        except KeyboardInterrupt:
            print("detached (host continues)", file=sys.stderr)
            return ok(detached=True, log_path=str(path), source=source)
        return ok(follow_ended=True, log_path=str(path), source=source)

    if scope_to_start and (marker_at or start_id):
        tail = read_log_since_marker(
            path,
            marker_timestamp=str(marker_at) if marker_at else None,
            start_id=str(start_id) if start_id else None,
            max_lines=lines_n,
        )
    else:
        tail = read_log_tail(path, max_lines=lines_n)
    if use_json:
        return ok(
            log_path=str(path),
            source=source,
            exists=path.is_file(),
            lines=tail,
            line_count=len(tail),
            pid=pid,
            since_start=since_start,
            start_marker_at=marker_at,
            start_id=start_id,
        )

    print(f"log={path} pid={pid} read_at={now_iso()}")
    if not path.is_file():
        print(f"(no log file yet at {path})", file=sys.stderr)
    else:
        for line in tail:
            print(line)
    return ok(log_path=str(path), source=source, line_count=len(tail), pid=pid)


def cmd_host_stop(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args, require_registry=False)
    if isinstance(ctx, dict):
        return ctx

    if not host_is_running(ctx.workspace):
        clear_state(ctx.workspace)
        return ok(stopped=True, was_running=False)

    key = getattr(args, "idempotency_key", None) or str(uuid.uuid4())
    state_before = read_state(ctx.workspace)
    pid = int(state_before.get("pid") or 0) if state_before else 0

    result = call_host(
        ctx.workspace,
        "host.stop",
        {"idempotency_key": key},
    )
    if not result.get("ok"):
        return result

    import time

    for _ in range(50):
        if not pid or not pid_alive(pid):
            break
        time.sleep(0.1)

    if pid and pid_alive(pid):
        return error("HOST_STOP_FAILED", f"Host process {pid} is still running")
    clear_state(ctx.workspace)
    return ok(stopped=True, was_running=True)


def cmd_host_run(args: argparse.Namespace) -> dict[str, Any]:
    """Foreground host (tests and debugging)."""
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    if host_is_running(ctx.workspace):
        return error(
            "HOST_ALREADY_RUNNING",
            "Another Foundry host is already running for this workspace",
        )
    code = run_host_process(
        ctx.workspace,
        Path(args.registry).resolve() if args.registry else None,
        auto_advance=bool(getattr(args, "auto_advance", False)),
        auto_advance_interval=float(getattr(args, "auto_advance_interval", None) or 2.0),
    )
    if code != 0:
        return error("HOST_EXITED", f"Host exited with code {code}")
    return ok(stopped=True)
