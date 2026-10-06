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

from foundry_cli.host.discovery import clear_state, write_state
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
    def __init__(self, workspace: Path, bundle: Path) -> None:
        self.workspace = workspace.resolve()
        self.bundle = bundle.resolve()
        self._stop_event = threading.Event()
        self._server: socketserver.ThreadingTCPServer | socketserver.ThreadingUnixStreamServer | None = None
        self.handlers = HostHandlers(
            self.workspace,
            self.bundle,
            on_stop=self.request_stop,
        )

    def request_stop(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            self._server.shutdown()

    def _bind_server(self) -> tuple[Any, str, str]:
        if sys.platform != "win32":
            sock_file = socket_path(self.workspace)
            sock_file.parent.mkdir(parents=True, exist_ok=True)
            if sock_file.exists():
                sock_file.unlink()
            server = socketserver.ThreadingUnixStreamServer(
                str(sock_file),
                _LineRequestHandler,
            )
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
        self._server, transport, address = self._bind_server()
        port = self._server.server_address[1] if transport == "tcp" else None
        write_state(
            self.workspace,
            pid=os.getpid(),
            transport=transport,
            address=address,
            port=port,
        )
        self.handlers.startup_recover()
        try:
            self._server.serve_forever(poll_interval=0.5)
        finally:
            self._server.server_close()
            clear_state(self.workspace)
            if transport == "unix":
                path = socket_path(self.workspace)
                if path.exists():
                    path.unlink()


def run_host_process(workspace: Path, registry: Path | None) -> int:
    ctx = resolve_host_context(workspace, registry)
    if isinstance(ctx, dict):
        print(json.dumps(ctx), file=sys.stderr)
        return 1
    server = HostServer(ctx.workspace, ctx.bundle)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.request_stop()
    return 0
