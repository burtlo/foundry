"""CLI client for the local job host control channel."""

from __future__ import annotations

import json
import socket
import sys
import uuid
from pathlib import Path
from typing import Any

from foundry_cli.errors import error, ok
from foundry_cli.host.discovery import host_is_running, pid_alive, read_state
from foundry_cli.host.paths import PROTOCOL_VERSION, socket_path
from foundry_cli.host.timeout_policy import client_timeout_for_method
def _connect(state: dict[str, Any]) -> socket.socket:
    transport = str(state.get("transport") or "tcp")
    if transport == "unix":
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(state.get("address")))
        return sock
    address = str(state.get("address") or "127.0.0.1:0")
    if ":" in address:
        host, port_text = address.rsplit(":", 1)
        port = int(port_text)
    else:
        host = "127.0.0.1"
        port = int(state.get("port") or 0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    return sock


def call_host(
    workspace: Path,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    if not host_is_running(workspace):
        return error("HOST_UNAVAILABLE", "Local Foundry host is not running")

    state = read_state(workspace)
    if not state:
        return error("HOST_UNAVAILABLE", "Host state file is missing")

    effective_timeout = (
        timeout
        if timeout is not None
        else client_timeout_for_method(method, params, workspace=workspace)
    )

    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "id": request_id or str(uuid.uuid4()),
        "method": method,
        "params": params or {},
    }
    line = json.dumps(payload, sort_keys=True) + "\n"

    try:
        sock = _connect(state)
        sock.settimeout(effective_timeout)
        sock.sendall(line.encode("utf-8"))
        buffer = b""
        while b"\n" not in buffer:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buffer += chunk
        sock.close()
    except OSError as exc:
        return error("HOST_UNAVAILABLE", f"Could not reach host: {exc}")

    if not buffer:
        return error("HOST_PROTOCOL_ERROR", "Empty response from host")

    try:
        response = json.loads(buffer.decode("utf-8").strip())
    except json.JSONDecodeError as exc:
        return error("HOST_PROTOCOL_ERROR", f"Invalid host response: {exc}")

    if not isinstance(response, dict):
        return error("HOST_PROTOCOL_ERROR", "Host response must be a JSON object")

    if response.get("ok"):
        result = response.get("result")
        if isinstance(result, dict):
            return result
        return ok(**(result or {}))

    err = response.get("error") if isinstance(response.get("error"), dict) else {}
    return error(
        str(err.get("code", "HOST_ERROR")),
        str(err.get("message", "Host request failed")),
        **{k: v for k, v in response.items() if k not in {"ok", "error", "id", "protocol_version"}},
    )


def host_status_payload(workspace: Path) -> dict[str, Any]:
    from foundry_cli.host.auto_advance_status import read_auto_advance_status
    from foundry_cli.host.paths import auto_advance_status_path, host_log_path, startup_log_path

    workspace = workspace.resolve()
    logs = {
        "host": str(host_log_path(workspace)),
        "startup": str(startup_log_path(workspace)),
    }
    state = read_state(workspace)
    if not state:
        return ok(running=False, host=None, logs=logs)
    pid = int(state.get("pid") or 0)
    running = pid_alive(pid)
    health: dict[str, Any] | None = None
    if running:
        health = call_host(workspace, "health")
        if not health.get("ok"):
            running = False
    auto_advance_enabled = bool(state.get("auto_advance"))
    auto_advance_interval = state.get("auto_advance_interval")
    auto_status = read_auto_advance_status(workspace) if auto_advance_enabled else None
    return ok(
        running=running,
        host={
            "pid": pid,
            "transport": state.get("transport"),
            "address": state.get("address"),
            "port": state.get("port"),
            "started_at": state.get("started_at"),
            "protocol_version": state.get("protocol_version"),
            "auto_advance": auto_advance_enabled,
            "auto_advance_interval": auto_advance_interval,
        },
        health=health if health and health.get("ok") else None,
        logs=logs,
        auto_advance_status=auto_status,
        auto_advance_status_path=str(auto_advance_status_path(workspace)),
    )
