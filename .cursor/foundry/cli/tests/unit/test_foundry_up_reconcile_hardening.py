"""P4 hardening wave 2: ``foundry up`` through real ``reconcile_bridge`` (no smoke URL)."""

from __future__ import annotations

import argparse
import json
import shutil
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest

from foundry_cli.bridge.discovery import read_state as read_bridge_state
from foundry_cli.bridge.discovery import write_state as write_bridge_state
from foundry_cli.bridge.paths import DEFAULT_BRIDGE_HOST, DEFAULT_BRIDGE_PORT
from foundry_cli.constants import OPERATOR_SMOKE_BRIDGE_URL_ENV
from foundry_cli.host.discovery import read_state as read_host_state
from foundry_cli.host_commands import cmd_host_stop
from foundry_cli.judgment_bridge.server import DEFAULT_AGENT_PATH
from foundry_cli.bridge.lifecycle import stop_bridge
from foundry_cli.up_commands import cmd_up
from tests.conftest import FOUNDRY_ROOT

pytestmark = pytest.mark.xdist_group(name="foundry_up_reconcile_hardening")

BUNDLE = FOUNDRY_ROOT
_HOST_POLL_INTERVAL_S = 0.05
_HOST_POLL_ATTEMPTS = 80


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    return workspace


def _up_args(workspace: Path) -> argparse.Namespace:
    return argparse.Namespace(
        workspace=str(workspace),
        registry=str(BUNDLE),
        json=True,
        foreground=False,
        skip_preflight=True,
    )


def _wait_for_host_running(workspace: Path) -> None:
    from foundry_cli.host.discovery import host_is_running
    import time

    for _ in range(_HOST_POLL_ATTEMPTS):
        if host_is_running(workspace):
            return
        time.sleep(_HOST_POLL_INTERVAL_S)
    raise AssertionError("host did not become ready")


class _BridgeHealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/health", "/healthz"):
            body = b'{"ok": true, "service": "test-bridge-health"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


def _start_default_bridge_health_server() -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer((DEFAULT_BRIDGE_HOST, DEFAULT_BRIDGE_PORT), _BridgeHealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


@contextmanager
def _bridge_reconcile_patches(mock_proc: MagicMock) -> Iterator[MagicMock]:
    """Patches for real ``reconcile_bridge`` without detached judgment_bridge spawn."""
    with patch("foundry_cli.bridge.lifecycle.pid_alive", return_value=True):
        with patch(
            "foundry_cli.bridge.lifecycle._probe_health",
            return_value={"ok": True, "detail": "healthy"},
        ):
            with patch("foundry_cli.judgment_bridge.keys.resolve_cursor_api_key"):
                with patch(
                    "foundry_cli.bridge.lifecycle._spawn_detached_bridge",
                    return_value=mock_proc,
                ) as spawn:
                    yield spawn


def test_cmd_up_twice_real_reconcile_spawns_bridge_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOUNDRY_CURSOR_API_KEY", "test-key")
    monkeypatch.delenv(OPERATOR_SMOKE_BRIDGE_URL_ENV, raising=False)

    workspace = _workspace(tmp_path)
    args = _up_args(workspace)
    mock_proc = MagicMock()
    mock_proc.pid = 5555
    health_server: ThreadingHTTPServer | None = None

    try:
        health_server, _ = _start_default_bridge_health_server()
        with _bridge_reconcile_patches(mock_proc) as spawn:
            first = cmd_up(args)
            _wait_for_host_running(workspace)
            host_pid_first = int((read_host_state(workspace) or {}).get("pid") or 0)
            assert host_pid_first > 0

            second = cmd_up(args)

        spawn.assert_called_once()
        assert first.get("ok") is True
        assert first.get("ready") is True
        assert second.get("ok") is True
        bridge = second.get("bridge") if isinstance(second.get("bridge"), dict) else {}
        assert bridge.get("already_running") is True

        host_pid_second = int((read_host_state(workspace) or {}).get("pid") or 0)
        assert host_pid_second == host_pid_first
    finally:
        cmd_host_stop(argparse.Namespace(workspace=str(workspace), registry=str(BUNDLE), json=True))
        stop_bridge(workspace.resolve())
        if health_server is not None:
            health_server.shutdown()


def test_cmd_up_reconciles_stale_bound_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOUNDRY_CURSOR_API_KEY", "test-key")
    monkeypatch.delenv(OPERATOR_SMOKE_BRIDGE_URL_ENV, raising=False)

    workspace = _workspace(tmp_path)
    fake_registry = tmp_path / "fake-registry"
    fake_registry.mkdir()
    write_bridge_state(
        workspace,
        pid=4242,
        listen_host=DEFAULT_BRIDGE_HOST,
        listen_port=DEFAULT_BRIDGE_PORT,
        agent_path=DEFAULT_AGENT_PATH,
        bound_workspace=fake_registry,
    )
    args = _up_args(workspace)
    mock_proc = MagicMock()
    mock_proc.pid = 6666
    health_server: ThreadingHTTPServer | None = None

    try:
        health_server, _ = _start_default_bridge_health_server()
        with _bridge_reconcile_patches(mock_proc) as spawn:
            with patch("foundry_cli.bridge.lifecycle._terminate_pid"):
                result = cmd_up(args)

        spawn.assert_called_once()
        assert result.get("ok") is True
        state = read_bridge_state(workspace)
        assert state is not None
        assert state.get("workspace") == str(workspace.resolve())
    finally:
        cmd_host_stop(argparse.Namespace(workspace=str(workspace), registry=str(BUNDLE), json=True))
        stop_bridge(workspace.resolve())
        if health_server is not None:
            health_server.shutdown()


def test_cmd_up_foreground_stops_tracked_bridge_pid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Foreground Ctrl+C stops bridge when reconcile reported a started PID (real reconcile path)."""
    monkeypatch.setenv("FOUNDRY_CURSOR_API_KEY", "test-key")
    monkeypatch.delenv(OPERATOR_SMOKE_BRIDGE_URL_ENV, raising=False)

    workspace = _workspace(tmp_path)
    args = _up_args(workspace)
    args.foreground = True
    mock_proc = MagicMock()
    mock_proc.pid = 4242
    health_server: ThreadingHTTPServer | None = None

    def _sleep_raise(_seconds: float) -> None:
        raise KeyboardInterrupt

    try:
        health_server, _ = _start_default_bridge_health_server()
        with _bridge_reconcile_patches(mock_proc):
            with patch("foundry_cli.up_commands.host_is_running", return_value=False):
                with patch("foundry_cli.up_commands.cmd_host_start") as host_start:
                    host_start.return_value = {
                        "ok": True,
                        "started": True,
                        "pid": 5252,
                    }
                    with patch("foundry_cli.up_commands.cmd_host_stop") as host_stop:
                        host_stop.return_value = {"ok": True, "stopped": True}
                        with patch("foundry_cli.up_commands.stop_bridge") as stop_bridge_mock:
                            stop_bridge_mock.return_value = {
                                "ok": True,
                                "stopped": True,
                            }
                            with patch("time.sleep", side_effect=_sleep_raise):
                                result = cmd_up(args)

        assert result.get("ok") is True
        assert result.get("foreground") is True
        shutdown = result.get("foreground_shutdown")
        assert isinstance(shutdown, dict)
        assert shutdown.get("shutdown") is True
        host_stop.assert_called()
        stop_bridge_mock.assert_called_once_with(workspace.resolve())
    finally:
        if health_server is not None:
            health_server.shutdown()


class _RegistryBridgeHealthHandler(BaseHTTPRequestHandler):
    """Simulates ``bridge start`` from registry context on the default listen port."""

    registry_workspace: str = ""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/health", "/healthz"):
            body = json.dumps(
                {
                    "ok": True,
                    "service": "registry-judgment-bridge",
                    "workspace": self.registry_workspace,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


def test_ac5_registry_foreground_bridge_then_app_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: registry bridge on default port, then ``foundry up`` binds bridge to app workspace.

    See ``docs/plans/foundry-up/gwt-scenario.md`` (wrong-workspace / registry-then-app scenario).
    """
    monkeypatch.setenv("FOUNDRY_CURSOR_API_KEY", "test-key")
    monkeypatch.delenv(OPERATOR_SMOKE_BRIDGE_URL_ENV, raising=False)

    workspace = _workspace(tmp_path)
    args = _up_args(workspace)
    foreign_server: ThreadingHTTPServer | None = None
    app_bridge_servers: list[ThreadingHTTPServer] = []

    _RegistryBridgeHealthHandler.registry_workspace = str(BUNDLE.resolve())

    def _spawn_side_effect(
        argv: list[str],
        *,
        bundle: Path,
        workspace: Path,
    ) -> MagicMock:
        port = int(argv[argv.index("--port") + 1])
        app_ws = str(workspace.resolve())

        class _AppBridgeHealthHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

            def do_GET(self) -> None:  # noqa: N802
                if self.path.rstrip("/") in ("/health", "/healthz"):
                    body = json.dumps(
                        {"ok": True, "service": "app-judgment-bridge", "workspace": app_ws}
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

        server = ThreadingHTTPServer((DEFAULT_BRIDGE_HOST, port), _AppBridgeHealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        app_bridge_servers.append(server)
        proc = MagicMock()
        proc.pid = 8888
        return proc

    try:
        foreign_server = ThreadingHTTPServer(
            (DEFAULT_BRIDGE_HOST, DEFAULT_BRIDGE_PORT),
            _RegistryBridgeHealthHandler,
        )
        foreign_thread = threading.Thread(target=foreign_server.serve_forever, daemon=True)
        foreign_thread.start()

        with patch("foundry_cli.bridge.lifecycle.pid_alive", return_value=True):
            with patch("foundry_cli.judgment_bridge.keys.resolve_cursor_api_key"):
                with patch(
                    "foundry_cli.bridge.lifecycle._spawn_detached_bridge",
                    side_effect=_spawn_side_effect,
                ) as spawn:
                    result = cmd_up(args)

        spawn.assert_called_once()
        argv = spawn.call_args[0][0]
        assert argv[argv.index("--workspace") + 1] == str(workspace.resolve())
        spawn_port = int(argv[argv.index("--port") + 1])
        assert spawn_port != DEFAULT_BRIDGE_PORT

        state = read_bridge_state(workspace)
        assert state is not None
        assert state.get("workspace") == str(workspace.resolve())
        assert int(state.get("listen_port") or 0) == spawn_port

        assert result.get("ok") is True
        bridge = result.get("bridge") if isinstance(result.get("bridge"), dict) else {}
        bridge_url = str(bridge.get("url") or "")
        assert f":{spawn_port}" in bridge_url
    finally:
        cmd_host_stop(argparse.Namespace(workspace=str(workspace), registry=str(BUNDLE), json=True))
        stop_bridge(workspace.resolve())
        for server in app_bridge_servers:
            server.shutdown()
        if foreign_server is not None:
            foreign_server.shutdown()
