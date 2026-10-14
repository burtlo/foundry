"""Process, health, and adapter readiness dimensions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from foundry_cli.host.client import call_host
from foundry_cli.host.discovery import host_is_running, pid_alive, read_state


def _probe_url_health(base_url: str, *, timeout: float = 2.0) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/health"
    try:
        with urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body) if body.strip() else {}
    except (URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
        return {"ok": False, "reachable": False, "detail": str(exc)}
    if isinstance(data, dict) and data.get("ok"):
        return {"ok": True, "reachable": True, "detail": "healthy"}
    return {"ok": False, "reachable": False, "detail": "unexpected health response"}


def bridge_readiness_from_url(bridge_url: str | None) -> dict[str, Any]:
    if not bridge_url:
        return {
            "ok": False,
            "configured": False,
            "reachable": False,
            "detail": "bridge URL not set",
        }
    parsed = urlparse(bridge_url)
    if parsed.scheme and parsed.netloc:
        base = f"{parsed.scheme}://{parsed.netloc}"
    else:
        base = bridge_url.rsplit("/", 1)[0] if "/" in bridge_url else bridge_url
    probe = _probe_url_health(base)
    return {
        "ok": bool(probe.get("ok")),
        "configured": True,
        "reachable": bool(probe.get("reachable")),
        "detail": probe.get("detail"),
        "url": bridge_url,
    }


def host_process_dimension(workspace: Path) -> dict[str, Any]:
    state = read_state(workspace)
    if not state:
        return {"ok": False, "running": False, "detail": "no host state", "pid": None}
    pid = int(state.get("pid") or 0)
    alive = pid_alive(pid)
    return {
        "ok": alive,
        "running": alive,
        "pid": pid if alive else None,
        "started_at": state.get("started_at"),
        "detail": "process running" if alive else "process not running",
    }


def host_health_dimension(workspace: Path) -> dict[str, Any]:
    if not host_is_running(workspace):
        return {"ok": False, "detail": "host unavailable"}
    health = call_host(workspace, "health", timeout=5.0)
    if health.get("ok"):
        return {"ok": True, "detail": "health RPC ok", "registry_valid": health.get("registry_valid")}
    return {
        "ok": False,
        "detail": str(health.get("error", {}).get("message") if isinstance(health.get("error"), dict) else health),
    }


def adapter_dimension(
    workspace: Path,
    *,
    expected_http_url: str | None,
) -> dict[str, Any]:
    state = read_state(workspace) or {}
    adapter_kind = str(state.get("agent_adapter") or "")
    http_url = str(state.get("agent_http_url") or "")
    configured = bool(adapter_kind) and (adapter_kind != "http" or bool(http_url))
    if adapter_kind == "http" and http_url:
        probe = bridge_readiness_from_url(http_url)
        matches = expected_http_url is None or http_url == expected_http_url
        return {
            "ok": bool(probe.get("ok")) and matches,
            "configured": configured,
            "reachable": bool(probe.get("reachable")),
            "adapter": adapter_kind or None,
            "http_url": http_url or None,
            "detail": probe.get("detail") if matches else "adapter URL does not match bridge",
            "recovery_hint": None if probe.get("ok") else "Run foundry up to reconcile bridge and host",
        }
    if not configured:
        return {
            "ok": False,
            "configured": False,
            "reachable": False,
            "detail": "adapter not configured on host",
            "recovery_hint": "Run foundry up",
        }
    return {
        "ok": configured,
        "configured": configured,
        "reachable": None,
        "adapter": adapter_kind,
        "http_url": http_url or None,
        "detail": "adapter configured",
    }
