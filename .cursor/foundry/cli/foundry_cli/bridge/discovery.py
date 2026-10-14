"""Judgment bridge discovery: pid, listen URL, workspace binding."""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from foundry_cli.bridge.paths import bridge_dir, spawn_lock_path, state_path
from foundry_cli.host.discovery import pid_alive, restrict_host_dir_permissions
from foundry_cli.util import now_iso


def write_state(
    workspace: Path,
    *,
    pid: int,
    listen_host: str,
    listen_port: int,
    agent_path: str,
    bound_workspace: Path,
    start_id: str | None = None,
) -> Path:
    restrict_host_dir_permissions(bridge_dir(workspace))
    payload: dict[str, Any] = {
        "pid": pid,
        "listen_host": listen_host,
        "listen_port": int(listen_port),
        "agent_path": agent_path if agent_path.startswith("/") else f"/{agent_path}",
        "workspace": str(bound_workspace.resolve()),
        "started_at": now_iso(),
    }
    if start_id:
        payload["start_id"] = start_id
    path = state_path(workspace)
    temp = path.with_suffix(".json.tmp")
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with temp.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    if sys.platform != "win32":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path


def read_state(workspace: Path) -> dict[str, Any] | None:
    path = state_path(workspace)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return None
    return data


def clear_state(workspace: Path) -> None:
    path = state_path(workspace)
    if path.is_file():
        path.unlink()


def bridge_http_url(state: dict[str, Any]) -> str:
    host = str(state.get("listen_host") or "127.0.0.1")
    port = int(state.get("listen_port") or 0)
    agent_path = str(state.get("agent_path") or "/v1/agent")
    if not agent_path.startswith("/"):
        agent_path = f"/{agent_path}"
    return f"http://{host}:{port}{agent_path}"


def bridge_health_base_url(state: dict[str, Any]) -> str:
    host = str(state.get("listen_host") or "127.0.0.1")
    port = int(state.get("listen_port") or 0)
    return f"http://{host}:{port}"


def bridge_is_running(workspace: Path) -> bool:
    state = read_state(workspace)
    if not state:
        return False
    pid = int(state.get("pid") or 0)
    return pid_alive(pid)


@contextmanager
def bridge_startup_lock(workspace: Path) -> Iterator[None]:
    """Brief lock while the CLI spawns a detached bridge."""
    directory = bridge_dir(workspace)
    restrict_host_dir_permissions(directory)
    lock_file = spawn_lock_path(workspace)
    from foundry_cli.host.discovery import _lock_file, _unlock_file

    with lock_file.open("a+b") as handle:
        _lock_file(handle, nonblocking=False)
        try:
            yield
        finally:
            _unlock_file(handle)
