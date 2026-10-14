"""Integration-style ``foundry up`` with in-thread mock bridge (no orphan bridge processes)."""

from __future__ import annotations

import argparse
import shutil
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_cli.host_commands import cmd_host_stop
from urllib.parse import urlparse

from foundry_cli.judgment_bridge.server import DEFAULT_AGENT_PATH, JudgmentBridgeHandler
from foundry_cli.operator_integration_smoke import mock_invoke_judgment
from foundry_cli.up_commands import cmd_up
from tests.conftest import FOUNDRY_ROOT

pytestmark = pytest.mark.xdist_group(name="foundry_up_integration")

_HOST_POLL_INTERVAL_S = 0.05
_HOST_POLL_ATTEMPTS = 80


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        FOUNDRY_ROOT / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    return workspace


def _start_mock_bridge(
    workspace: Path,
    bundle: Path,
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    agent_path = DEFAULT_AGENT_PATH

    class Handler(JudgmentBridgeHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in ("/health", "/healthz", "/v1/health"):
                self._send_json(200, {"ok": True, "service": "foundry-judgment-bridge"})
                return
            self._send_json(404, {"ok": False, "error": "not_found"})

    Handler.workspace = workspace.resolve()
    Handler.foundry_bundle = bundle.resolve()
    Handler.agent_path = agent_path

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    patch_target = "foundry_cli.judgment_bridge.server.invoke_judgment"

    def serve_with_mock() -> None:
        with patch(patch_target, side_effect=mock_invoke_judgment):
            server.serve_forever()

    thread = threading.Thread(target=serve_with_mock, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    url = f"http://127.0.0.1:{port}{agent_path}"
    return server, thread, url


def _wait_for_host_running(workspace: Path) -> None:
    from foundry_cli.host.discovery import host_is_running
    import time

    for _ in range(_HOST_POLL_ATTEMPTS):
        if host_is_running(workspace):
            return
        time.sleep(_HOST_POLL_INTERVAL_S)
    raise AssertionError("host did not become ready")


def test_foundry_up_starts_host_against_mock_bridge(tmp_path: Path) -> None:
    bundle = FOUNDRY_ROOT
    workspace = _workspace(tmp_path)
    bridge_server: ThreadingHTTPServer | None = None
    args = argparse.Namespace(
        workspace=str(workspace),
        registry=str(bundle),
        json=True,
        foreground=False,
        skip_preflight=True,
    )

    try:
        bridge_server, _bridge_thread, bridge_url = _start_mock_bridge(workspace, bundle)
        reconcile_payload = {
            "ok": True,
            "already_running": True,
            "started": False,
            "bridge_url": bridge_url,
            "workspace": str(workspace),
            "health": {"ok": True},
        }

        with patch("foundry_cli.up_commands.reconcile_bridge", return_value=reconcile_payload):
            result = cmd_up(args)

        assert result.get("ok") is True
        assert result.get("ready") is True
        assert (result.get("bridge") or {}).get("ok") is True
        _wait_for_host_running(workspace)
    finally:
        stop_args = argparse.Namespace(
            workspace=str(workspace),
            registry=str(bundle),
            json=True,
        )
        cmd_host_stop(stop_args)
        if bridge_server is not None:
            bridge_server.shutdown()
