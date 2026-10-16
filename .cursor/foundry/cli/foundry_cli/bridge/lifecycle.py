"""Start, stop, and reconcile the judgment bridge for a workspace."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from foundry_cli.bridge.discovery import (
    bridge_health_base_url,
    bridge_http_url,
    bridge_is_running,
    bridge_startup_lock,
    clear_state,
    read_state,
    write_state,
)
from foundry_cli.bridge.paths import DEFAULT_BRIDGE_HOST, DEFAULT_BRIDGE_PORT, log_path
from foundry_cli.errors import error, ok
from foundry_cli.host.discovery import pid_alive
from foundry_cli.judgment_bridge.server import DEFAULT_AGENT_PATH
from foundry_cli.detached_spawn import detached_python_executable, popen_kwargs_for_detached_child
from foundry_cli.spawn_env import child_process_env


def _probe_health(
    base_url: str,
    *,
    timeout: float = 2.0,
    expected_workspace: Path | None = None,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/health"
    try:
        with urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body) if body.strip() else {}
    except (URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
        return {"ok": False, "detail": str(exc)}
    if isinstance(data, dict) and data.get("ok"):
        if expected_workspace is not None:
            reported = data.get("workspace")
            if reported is not None and str(reported) != str(expected_workspace.resolve()):
                return {"ok": False, "detail": "foreign_workspace"}
        return {"ok": True, "detail": "healthy"}
    return {"ok": False, "detail": "unexpected health response"}


def _pick_free_tcp_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _spawn_detached_bridge(
    argv: list[str],
    *,
    bundle: Path,
    workspace: Path,
) -> subprocess.Popen[Any]:
    log_file = log_path(workspace)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_file.open("a", encoding="utf-8")
    env = child_process_env(bundle)
    kwargs: dict[str, Any] = {
        "cwd": str(workspace),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": log_handle,
        "env": env,
    }
    kwargs.update(popen_kwargs_for_detached_child())
    return subprocess.Popen(argv, **kwargs)


def _terminate_pid(pid: int) -> None:
    if pid <= 0 or not pid_alive(pid):
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        return
    import os

    try:
        os.kill(pid, 15)
    except OSError:
        pass


def stop_bridge(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    state = read_state(workspace)
    if not state:
        return ok(stopped=True, was_running=False)
    pid = int(state.get("pid") or 0)
    was = pid_alive(pid)
    if was:
        _terminate_pid(pid)
    clear_state(workspace)
    return ok(stopped=True, was_running=was)


def _workspace_matches(state: dict[str, Any], workspace: Path) -> bool:
    bound = str(state.get("workspace") or "")
    return bound == str(workspace.resolve())


def _normalize_agent_path(agent_path: str) -> str:
    return agent_path if agent_path.startswith("/") else f"/{agent_path}"


def _reconcile_config_matches(
    state: dict[str, Any],
    *,
    listen_host: str,
    listen_port: int,
    agent_path: str,
) -> bool:
    if str(state.get("listen_host") or "") != listen_host:
        return False
    if int(state.get("listen_port") or 0) != int(listen_port):
        return False
    stored = str(state.get("agent_path") or "")
    return stored == _normalize_agent_path(agent_path)


def reconcile_bridge(
    workspace: Path,
    bundle: Path,
    *,
    listen_host: str = DEFAULT_BRIDGE_HOST,
    listen_port: int = DEFAULT_BRIDGE_PORT,
    agent_path: str = DEFAULT_AGENT_PATH,
) -> dict[str, Any]:
    """Ensure a healthy bridge is bound to this workspace; restart when misconfigured."""
    workspace = workspace.resolve()
    bundle = bundle.resolve()
    state = read_state(workspace)
    if state and pid_alive(int(state.get("pid") or 0)):
        health = _probe_health(
            bridge_health_base_url(state),
            expected_workspace=workspace,
        )
        if (
            health.get("ok")
            and _workspace_matches(state, workspace)
            and _reconcile_config_matches(
                state,
                listen_host=listen_host,
                listen_port=listen_port,
                agent_path=agent_path,
            )
        ):
            return ok(
                already_running=True,
                bridge_url=bridge_http_url(state),
                pid=int(state.get("pid") or 0),
                workspace=str(workspace),
                health=health,
            )
        stop_bridge(workspace)

    try:
        from foundry_cli.judgment_bridge.keys import resolve_cursor_api_key

        resolve_cursor_api_key()
    except RuntimeError as exc:
        return error("CONFIGURATION_ERROR", str(exc))

    start_id = str(uuid.uuid4())
    with bridge_startup_lock(workspace):
        if bridge_is_running(workspace):
            state = read_state(workspace)
            if state and _workspace_matches(state, workspace):
                health = _probe_health(
                    bridge_health_base_url(state),
                    expected_workspace=workspace,
                )
                if health.get("ok") and _reconcile_config_matches(
                    state,
                    listen_host=listen_host,
                    listen_port=listen_port,
                    agent_path=agent_path,
                ):
                    return ok(
                        already_running=True,
                        bridge_url=bridge_http_url(state),
                        pid=int(state.get("pid") or 0),
                        workspace=str(workspace),
                        health=health,
                    )
            stop_bridge(workspace)

        spawn_port = int(listen_port)
        if spawn_port == DEFAULT_BRIDGE_PORT:
            default_probe = _probe_health(
                f"http://{listen_host}:{spawn_port}",
                expected_workspace=workspace,
            )
            if default_probe.get("detail") == "foreign_workspace":
                bind_host = "127.0.0.1" if listen_host in ("0.0.0.0", "") else listen_host
                spawn_port = _pick_free_tcp_port(bind_host)

        argv = [
            detached_python_executable(),
            "-m",
            "foundry_cli.judgment_bridge",
            "--workspace",
            str(workspace),
            "--registry",
            str(bundle),
            "--host",
            listen_host,
            "--port",
            str(spawn_port),
            "--path",
            agent_path,
        ]
        proc = _spawn_detached_bridge(argv, bundle=bundle, workspace=workspace)

    import time

    for _ in range(80):
        if not pid_alive(proc.pid):
            break
        probe = _probe_health(
            f"http://{listen_host}:{spawn_port}",
            expected_workspace=workspace,
        )
        if probe.get("ok"):
            write_state(
                workspace,
                pid=proc.pid,
                listen_host=listen_host,
                listen_port=spawn_port,
                agent_path=agent_path,
                bound_workspace=workspace,
                start_id=start_id,
            )
            state = read_state(workspace) or {}
            return ok(
                started=True,
                bridge_url=bridge_http_url(state),
                pid=proc.pid,
                workspace=str(workspace),
                health=probe,
                start_id=start_id,
            )
        time.sleep(0.1)

    stop_bridge(workspace)
    return error(
        "BRIDGE_START_FAILED",
        "Judgment bridge did not become healthy in time",
    )
