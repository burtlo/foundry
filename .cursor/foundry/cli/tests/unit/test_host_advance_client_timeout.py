"""Host run.advance client timeout with slow agent adapter (integration)."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.agent.adapter import StubAgentAdapter
from foundry_cli.host.client import call_host
from foundry_cli.host.discovery import host_is_running
from foundry_cli.host.handlers import HostHandlers
from foundry_cli.host.server import HostServer
from foundry_cli.run_store import get_revision, load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import intake_open_run, shape_test_workspace

BUNDLE = FOUNDRY_ROOT
_SLOW_ADAPTER_DELAY_SECONDS = 2.0


class _SlowStubAdapter(StubAgentAdapter):
    def __init__(self, delay_seconds: float) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds

    def invoke(self, request):  # noqa: ANN001
        time.sleep(self.delay_seconds)
        return super().invoke(request)


def _park_run_at_agent_wait(workspace: Path) -> tuple[str, int]:
    run_dir, snapshot, flow = intake_open_run(workspace, work_prompt="Slow adapter timeout test")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert snapshot.get("wait", {}).get("kind") == "agent"
    run_id = str(snapshot.get("run_id") or "adv-0001")
    revision = get_revision(snapshot)
    assert revision == get_revision(load_snapshot(run_dir))
    return run_id, revision


@pytest.mark.skipif(sys.platform == "win32", reason="Unix socket host bind")
def test_run_advance_slow_adapter_succeeds_with_policy_timeout(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_id, revision = _park_run_at_agent_wait(workspace)

    server = HostServer(workspace, BUNDLE)
    server.handlers = HostHandlers(
        workspace,
        BUNDLE,
        on_stop=server.request_stop,
        agent_adapter=_SlowStubAdapter(_SLOW_ADAPTER_DELAY_SECONDS),
    )
    server.handlers.startup_recover = lambda: []  # type: ignore[method-assign]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for _ in range(50):
            if host_is_running(workspace):
                break
            time.sleep(0.05)
        assert host_is_running(workspace)

        started = time.monotonic()
        result = call_host(
            workspace,
            "run.advance",
            {
                "run_id": run_id,
                "expected_revision": revision,
                "step_budget": 1,
                "idempotency_key": "slow-adapter-timeout-test",
            },
        )
        elapsed = time.monotonic() - started
        assert result.get("ok") is True, result
        assert elapsed >= _SLOW_ADAPTER_DELAY_SECONDS
    finally:
        server.request_stop()
        thread.join(timeout=10)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix socket host bind")
def test_run_advance_slow_adapter_fails_with_short_explicit_timeout(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_id, revision = _park_run_at_agent_wait(workspace)

    server = HostServer(workspace, BUNDLE)
    server.handlers = HostHandlers(
        workspace,
        BUNDLE,
        on_stop=server.request_stop,
        agent_adapter=_SlowStubAdapter(_SLOW_ADAPTER_DELAY_SECONDS),
    )
    server.handlers.startup_recover = lambda: []  # type: ignore[method-assign]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for _ in range(50):
            if host_is_running(workspace):
                break
            time.sleep(0.05)
        assert host_is_running(workspace)

        result = call_host(
            workspace,
            "run.advance",
            {
                "run_id": run_id,
                "expected_revision": revision,
                "step_budget": 1,
                "idempotency_key": "slow-adapter-short-timeout",
            },
            timeout=0.5,
        )
        assert result.get("ok") is False
        err = result.get("error") if isinstance(result.get("error"), dict) else {}
        assert err.get("code") == "HOST_UNAVAILABLE"
    finally:
        server.request_stop()
        thread.join(timeout=10)
