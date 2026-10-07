"""TCP / Unix-socket server for the local job host."""

from __future__ import annotations

import json
import os
import socket
import socketserver
import sys
import threading
from pathlib import Path
from typing import Any

from foundry_cli.host.discovery import (
    HostDiscoveryError,
    acquire_host_ownership,
    append_startup_log,
    clear_state,
    pid_alive,
    read_state,
    release_host_ownership,
    write_state,
)
from foundry_cli.host.auto_advance import AutoAdvanceLoop
from foundry_cli.host.auto_advance_status import clear_auto_advance_status
from foundry_cli.host.logging_config import configure_host_logging
from foundry_cli.host.handlers import HostHandlers, resolve_host_context
from foundry_cli.host.paths import socket_path
from foundry_cli.host.protocol import (
    ProtocolError,
    encode_response,
    error_response,
    parse_request_line,
    success_response,
)


class _LineRequestHandler(socketserver.StreamRequestHandler):
    handlers: HostHandlers
    stop_event: threading.Event

    def handle(self) -> None:
        while not self.stop_event.is_set():
            line = self.rfile.readline()
            if not line:
                break
            try:
                request = parse_request_line(line.decode("utf-8"))
                result = self.handlers.dispatch(
                    request["method"],
                    request["params"],
                    request["id"],
                )
                if result.get("ok"):
                    response = success_response(request["id"], result)
                else:
                    err = result.get("error") or {}
                    response = error_response(
                        request["id"],
                        str(err.get("code", "HOST_ERROR")),
                        str(err.get("message", "Operation failed")),
                        **{k: v for k, v in result.items() if k not in {"ok", "error"}},
                    )
            except ProtocolError as exc:
                response = error_response("unknown", exc.code, exc.message, **exc.extra)
                request = {}
            except Exception as exc:  # noqa: BLE001 — surface as protocol error
                response = error_response("unknown", "HOST_ERROR", str(exc))
                request = {}
            self.wfile.write(encode_response(response))
            self.wfile.flush()
            if request.get("method") == "host.stop" and response.get("ok"):
                break


class HostServer:
    def __init__(
        self,
        workspace: Path,
        bundle: Path,
        *,
        auto_advance: bool = False,
        auto_advance_interval: float = 2.0,
    ) -> None:
        self.workspace = workspace.resolve()
        self.bundle = bundle.resolve()
        self._auto_advance_enabled = bool(auto_advance)
        self._auto_advance_interval = float(auto_advance_interval)
        self._stop_event = threading.Event()
        self._server: socketserver.ThreadingTCPServer | socketserver.ThreadingUnixStreamServer | None = None
        self._ownership_handle: Any = None
        self._unix_socket_path: Path | None = None
        self._auto_advance_loop: AutoAdvanceLoop | None = None
        self.handlers = HostHandlers(
            self.workspace,
            self.bundle,
            on_stop=self.request_stop,
        )
        if self._auto_advance_enabled:
            self._auto_advance_loop = AutoAdvanceLoop(
                workspace=self.workspace,
                bundle=self.bundle,
                agent_adapter=self.handlers._agent_adapter,
                interval_seconds=self._auto_advance_interval,
                stop_event=self._stop_event,
            )

    def request_stop(self) -> None:
        self._stop_event.set()
        if self._auto_advance_loop is not None:
            self._auto_advance_loop.stop()
        if self._server is not None:
            self._server.shutdown()

    def _prepare_unix_socket(self, sock_file: Path) -> None:
        if sock_file.exists():
            state = read_state(self.workspace)
            if state:
                pid = int(state.get("pid") or 0)
                if pid > 0 and pid_alive(pid):
                    raise HostDiscoveryError(
                        "HOST_ALREADY_RUNNING",
                        f"Unix socket already exists and host pid {pid} is alive",
                    )
            try:
                sock_file.unlink()
            except OSError as exc:
                raise HostDiscoveryError(
                    "HOST_BIND_FAILED",
                    f"Could not remove stale socket {sock_file}: {exc}",
                ) from exc
        sock_file.parent.mkdir(parents=True, exist_ok=True)

    def _bind_server(self) -> tuple[Any, str, str]:
        if sys.platform != "win32":
            sock_file = socket_path(self.workspace)
            self._prepare_unix_socket(sock_file)
            self._unix_socket_path = sock_file
            try:
                server = socketserver.ThreadingUnixStreamServer(
                    str(sock_file),
                    _LineRequestHandler,
                )
            except OSError as exc:
                raise HostDiscoveryError(
                    "HOST_BIND_FAILED",
                    f"Failed to bind Unix socket at {sock_file}: {exc}",
                ) from exc
            _LineRequestHandler.handlers = self.handlers
            _LineRequestHandler.stop_event = self._stop_event
            return server, "unix", str(sock_file)

        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _LineRequestHandler)
        server.allow_reuse_address = True
        _LineRequestHandler.handlers = self.handlers
        _LineRequestHandler.stop_event = self._stop_event
        host, port = server.server_address
        return server, "tcp", f"{host}:{port}"

    def serve_forever(self) -> None:
        configure_host_logging(self.workspace)
        try:
            self._ownership_handle = acquire_host_ownership(self.workspace)
        except HostDiscoveryError as exc:
            append_startup_log(self.workspace, f"{exc.code}: {exc.message}")
            raise

        try:
            self._server, transport, address = self._bind_server()
        except HostDiscoveryError as exc:
            append_startup_log(self.workspace, f"{exc.code}: {exc.message}")
            release_host_ownership(self._ownership_handle)
            self._ownership_handle = None
            raise

        port = self._server.server_address[1] if transport == "tcp" else None
        write_state(
            self.workspace,
            pid=os.getpid(),
            transport=transport,
            address=address,
            port=port,
            auto_advance=self._auto_advance_enabled,
            auto_advance_interval=self._auto_advance_interval,
        )
        self.handlers.startup_recover()
        if self._auto_advance_loop is not None:
            self._auto_advance_loop.start()
        try:
            self._server.serve_forever(poll_interval=0.5)
        finally:
            if self._auto_advance_loop is not None:
                self._auto_advance_loop.stop()
            self._server.server_close()
            clear_state(self.workspace)
            clear_auto_advance_status(self.workspace)
            if transport == "unix" and self._unix_socket_path is not None:
                if self._unix_socket_path.exists():
                    try:
                        self._unix_socket_path.unlink()
                    except OSError:
                        pass
            if self._ownership_handle is not None:
                release_host_ownership(self._ownership_handle)
                self._ownership_handle = None


def run_host_process(
    workspace: Path,
    registry: Path | None,
    *,
    auto_advance: bool = False,
    auto_advance_interval: float = 2.0,
) -> int:
    ctx = resolve_host_context(workspace, registry)
    if isinstance(ctx, dict):
        print(json.dumps(ctx), file=sys.stderr)
        return 1
    server = HostServer(
        ctx.workspace,
        ctx.bundle,
        auto_advance=auto_advance,
        auto_advance_interval=auto_advance_interval,
    )
    try:
        server.serve_forever()
    except HostDiscoveryError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {"code": exc.code, "message": exc.message},
                }
            ),
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        server.request_stop()
    return 0
