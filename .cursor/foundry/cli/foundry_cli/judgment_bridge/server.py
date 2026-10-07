"""HTTP server implementing the Foundry agent adapter POST contract."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from foundry_cli.judgment_bridge.cursor_provider import invoke_judgment

logger = logging.getLogger(__name__)

DEFAULT_AGENT_PATH = "/v1/agent"


class JudgmentBridgeHandler(BaseHTTPRequestHandler):
    workspace: Path
    foundry_bundle: Path
    agent_path: str

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        logger.info("%s - %s", self.address_string(), format % args)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/health", "/healthz"):
            self._send_json(200, {"ok": True, "service": "foundry-judgment-bridge"})
            return
        self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != self.agent_path:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"ok": False, "error": "body_must_be_object"})
            return
        request = payload.get("request")
        if not isinstance(request, dict):
            self._send_json(400, {"ok": False, "error": "missing_request_object"})
            return
        try:
            response_body = invoke_judgment(
                request,
                workspace=self.workspace,
                foundry_bundle=self.foundry_bundle,
            )
        except Exception as exc:  # noqa: BLE001 — surface to HTTP client
            logger.exception("judgment invoke failed")
            self._send_json(502, {"ok": False, "error": str(exc)})
            return
        self._send_json(200, response_body)

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve_judgment_bridge(
    *,
    host: str,
    port: int,
    workspace: Path,
    foundry_bundle: Path,
    agent_path: str = DEFAULT_AGENT_PATH,
) -> None:
    normalized_path = agent_path if agent_path.startswith("/") else f"/{agent_path}"

    class _Handler(JudgmentBridgeHandler):
        pass

    _Handler.workspace = workspace.resolve()
    _Handler.foundry_bundle = foundry_bundle.resolve()
    _Handler.agent_path = normalized_path

    server = ThreadingHTTPServer((host, port), _Handler)
    url = f"http://{host}:{port}{normalized_path}"
    logger.info("Judgment bridge listening on %s (workspace=%s)", url, workspace)
    print(f"foundry judgment bridge: {url}", flush=True)
    print(
        "Set FOUNDRY_AGENT_HTTP_URL to this URL on the job host before foundry host start",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Judgment bridge stopped")
    finally:
        server.server_close()
