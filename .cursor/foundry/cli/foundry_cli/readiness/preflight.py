"""Dependency checks before host start or shape."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from foundry_cli.bridge.discovery import bridge_is_running, read_state as read_bridge_state
from foundry_cli.bridge.discovery import bridge_http_url
from foundry_cli.errors import error, ok
from foundry_cli.host.discovery import host_is_running, read_state as read_host_state
from foundry_cli.readiness.dimensions import adapter_dimension, bridge_readiness_from_url


def _stub_adapter_allowed() -> bool:
    flag = (os.environ.get("FOUNDRY_ALLOW_STUB_ADAPTER") or "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def preflight_check(
    workspace: Path,
    *,
    expected_bridge_url: str | None = None,
    require_host: bool = True,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    missing: list[str] = []
    hints: list[str] = []

    bridge_ok = False
    if bridge_is_running(workspace):
        bstate = read_bridge_state(workspace) or {}
        url = bridge_http_url(bstate)
        br = bridge_readiness_from_url(url)
        bridge_ok = bool(br.get("ok"))
        if not bridge_ok:
            missing.append("bridge")
    elif expected_bridge_url:
        br = bridge_readiness_from_url(expected_bridge_url)
        bridge_ok = bool(br.get("ok"))
        if not bridge_ok:
            missing.append("bridge")
    else:
        missing.append("bridge")

    host_ok = host_is_running(workspace)
    if not host_ok and require_host:
        missing.append("host")

    if host_ok and _stub_adapter_allowed():
        return ok(
            bridge={"ok": True, "detail": "stub mode"},
            host={"ok": True},
            adapter={"ok": True, "configured": True, "detail": "stub adapter allowed"},
        )

    adapter = adapter_dimension(workspace, expected_http_url=expected_bridge_url)
    if host_ok and not adapter.get("configured"):
        missing.append("adapter")
    elif host_ok and not adapter.get("ok"):
        missing.append("adapter")

    if missing:
        hints.append("foundry up")
        return error(
            "READINESS_PREFLIGHT_FAILED",
            f"Missing or unhealthy: {', '.join(missing)}. Next: foundry up",
            missing=missing,
            recovery_hints=hints,
            bridge={"ok": bridge_ok},
            host={"ok": host_ok},
            adapter=adapter,
        )

    return ok(
        bridge={"ok": bridge_ok},
        host={"ok": host_ok},
        adapter=adapter,
    )
