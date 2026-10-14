"""``foundry up`` — reconcile bridge and host, print readiness."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path
from typing import Any

from foundry_cli.bridge.lifecycle import reconcile_bridge, stop_bridge
from foundry_cli.command_context import CommandContext
from foundry_cli.errors import error, ok
from foundry_cli.host.discovery import host_is_running
from foundry_cli.host_commands import cmd_host_start, cmd_host_stop
from foundry_cli.constants import OPERATOR_SMOKE_BRIDGE_URL_ENV
from foundry_cli.readiness.dimensions import (
    adapter_dimension,
    bridge_readiness_from_url,
    host_health_dimension,
    host_process_dimension,
)

# Stable alias for tests and operator_integration_smoke imports.
_OPERATOR_SMOKE_BRIDGE_URL_ENV = OPERATOR_SMOKE_BRIDGE_URL_ENV


def _readiness_payload(
    workspace: Path,
    *,
    bridge_url: str | None,
    bridge_section: dict[str, Any] | None,
) -> dict[str, Any]:
    bridge_dim = bridge_readiness_from_url(bridge_url) if bridge_url else {"ok": False, "detail": "no bridge"}
    if bridge_section:
        bridge_dim = {**bridge_dim, **{k: v for k, v in bridge_section.items() if k not in bridge_dim}}
    return {
        "workspace": str(workspace.resolve()),
        "bridge": bridge_dim,
        "host": {
            "process": host_process_dimension(workspace),
            "health": host_health_dimension(workspace),
        },
        "adapter": adapter_dimension(workspace, expected_http_url=bridge_url),
    }


def _reconcile_bridge_for_up(workspace: Path, bundle: Path) -> dict[str, Any]:
    """Reconcile bridge; honor integration-smoke URL injection (no detached bridge spawn)."""
    override = (os.environ.get(_OPERATOR_SMOKE_BRIDGE_URL_ENV) or "").strip()
    if override:
        health = bridge_readiness_from_url(override)
        return ok(
            already_running=True,
            started=False,
            bridge_url=override,
            workspace=str(workspace.resolve()),
            health={
                "ok": bool(health.get("ok")),
                "detail": health.get("detail"),
            },
        )
    return reconcile_bridge(workspace, bundle)


def _all_ready(payload: dict[str, Any]) -> bool:
    bridge = payload.get("bridge") if isinstance(payload.get("bridge"), dict) else {}
    host = payload.get("host") if isinstance(payload.get("host"), dict) else {}
    process = host.get("process") if isinstance(host.get("process"), dict) else {}
    health = host.get("health") if isinstance(host.get("health"), dict) else {}
    adapter = payload.get("adapter") if isinstance(payload.get("adapter"), dict) else {}
    return bool(bridge.get("ok") and process.get("ok") and health.get("ok") and adapter.get("ok"))


def cmd_up(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    workspace = ctx.workspace.resolve()
    foreground = bool(getattr(args, "foreground", False))
    bridge_children: list[int] = []
    host_children: list[int] = []

    bridge_result = _reconcile_bridge_for_up(workspace, ctx.bundle)
    if not bridge_result.get("ok"):
        return bridge_result
    bridge_url = str(bridge_result.get("bridge_url") or "")
    if bridge_result.get("started") and bridge_result.get("pid"):
        bridge_children.append(int(bridge_result["pid"]))

    host_extra = {
        "FOUNDRY_AGENT_ADAPTER": "http",
        "FOUNDRY_AGENT_HTTP_URL": bridge_url,
    }
    setattr(args, "_host_spawn_env", host_extra)

    if host_is_running(workspace):
        from foundry_cli.readiness.dimensions import adapter_dimension as _ad

        current = _ad(workspace, expected_http_url=bridge_url)
        if not current.get("ok"):
            stopped = cmd_host_stop(args)
            if not stopped.get("ok"):
                return stopped
            host_children.clear()
    else:
        host_children.clear()

    if not host_is_running(workspace):
        started = cmd_host_start(args)
        if not started.get("ok"):
            return started
        if started.get("pid"):
            host_children.append(int(started["pid"]))

    payload = _readiness_payload(
        workspace,
        bridge_url=bridge_url,
        bridge_section={
            "url": bridge_url,
            "pid": bridge_result.get("pid"),
            "already_running": bridge_result.get("already_running"),
        },
    )

    if foreground:
        print("foundry up: foreground mode — Ctrl+C stops bridge and host from this invocation", file=sys.stderr)
        try:
            signal.signal(signal.SIGINT, signal.default_int_handler)
            while True:
                import time

                time.sleep(3600)
        except KeyboardInterrupt:
            summary: dict[str, Any] = {"shutdown": True}
            for pid in reversed(host_children):
                cmd_host_stop(args)
            for _pid in reversed(bridge_children):
                stop_bridge(workspace)
            summary["message"] = "Stopped children started by this up invocation"
            payload["foreground_shutdown"] = summary
            return ok(ready=False, foreground=True, **payload)

    ready = _all_ready(payload)
    result = ok(ready=ready, **payload)
    if not ready:
        result["ok"] = False
        result["error"] = {
            "code": "READINESS_INCOMPLETE",
            "message": "One or more readiness dimensions are not ready",
        }
    return result
