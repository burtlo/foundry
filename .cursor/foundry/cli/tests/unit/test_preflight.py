"""Readiness preflight checks."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_cli.readiness.preflight import preflight_check


class _HealthHandler(BaseHTTPRequestHandler):
    healthy: bool = True

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/health", "/healthz"):
            body = {"ok": True, "service": "test-bridge"} if self.healthy else {"ok": False}
            payload = json.dumps(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()


def _start_health_server(*, healthy: bool = True) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    handler = type("Handler", (_HealthHandler,), {"healthy": healthy})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    agent_url = f"http://127.0.0.1:{port}/v1/agent"
    return server, thread, agent_url


def test_preflight_readiness_failed_missing_bridge_and_host(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()

    with patch("foundry_cli.readiness.preflight.bridge_is_running", return_value=False):
        with patch("foundry_cli.readiness.preflight.host_is_running", return_value=False):
            result = preflight_check(workspace)

    assert result.get("ok") is False
    err = result.get("error") or {}
    assert err.get("code") == "READINESS_PREFLIGHT_FAILED"
    assert "bridge" in (result.get("missing") or [])
    assert "host" in (result.get("missing") or [])
    assert result.get("recovery_hints") == ["foundry up"]


def test_preflight_fails_when_expected_bridge_unhealthy(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    server, _thread, agent_url = _start_health_server(healthy=False)
    try:
        with patch("foundry_cli.readiness.preflight.bridge_is_running", return_value=False):
            with patch("foundry_cli.readiness.preflight.host_is_running", return_value=False):
                result = preflight_check(workspace, expected_bridge_url=agent_url)
    finally:
        server.shutdown()

    assert result.get("ok") is False
    assert (result.get("error") or {}).get("code") == "READINESS_PREFLIGHT_FAILED"
    assert "bridge" in (result.get("missing") or [])


def test_preflight_stub_bypass_with_allow_flag_not_pytest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("FOUNDRY_ALLOW_STUB_ADAPTER", "1")

    with patch("foundry_cli.readiness.preflight.bridge_is_running", return_value=False):
        with patch("foundry_cli.readiness.preflight.host_is_running", return_value=True):
            result = preflight_check(workspace)

    assert result.get("ok") is True
    adapter = result.get("adapter") or {}
    assert adapter.get("ok") is True
    assert adapter.get("configured") is True
    assert "stub" in str(adapter.get("detail", "")).lower()


def test_preflight_no_stub_bypass_without_allow_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("FOUNDRY_ALLOW_STUB_ADAPTER", raising=False)

    server, _thread, agent_url = _start_health_server(healthy=True)
    try:
        with patch("foundry_cli.readiness.preflight.bridge_is_running", return_value=False):
            with patch("foundry_cli.readiness.preflight.host_is_running", return_value=True):
                with patch(
                    "foundry_cli.readiness.preflight.adapter_dimension",
                    return_value={
                        "ok": False,
                        "configured": False,
                        "detail": "adapter not configured on host",
                    },
                ):
                    result = preflight_check(workspace, expected_bridge_url=agent_url)
    finally:
        server.shutdown()

    assert result.get("ok") is False
    assert (result.get("error") or {}).get("code") == "READINESS_PREFLIGHT_FAILED"
    assert "adapter" in (result.get("missing") or [])


def test_preflight_ok_when_bridge_expected_url_healthy_and_adapter_ok(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    server, _thread, agent_url = _start_health_server(healthy=True)
    try:
        with patch("foundry_cli.readiness.preflight.bridge_is_running", return_value=False):
            with patch("foundry_cli.readiness.preflight.host_is_running", return_value=True):
                with patch(
                    "foundry_cli.readiness.preflight.adapter_dimension",
                    return_value={"ok": True, "configured": True},
                ):
                    result = preflight_check(workspace, expected_bridge_url=agent_url)
    finally:
        server.shutdown()

    assert result.get("ok") is True
    assert (result.get("bridge") or {}).get("ok") is True
    assert (result.get("host") or {}).get("ok") is True
