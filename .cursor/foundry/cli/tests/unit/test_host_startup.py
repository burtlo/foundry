"""Host accepts RPC while startup recovery runs."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from foundry_cli.host.client import call_host
from foundry_cli.host.server import HostServer


def test_host_health_available_during_slow_startup_recover(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "cli").mkdir(parents=True)
    (tmp_path / ".foundry").mkdir(parents=True, exist_ok=True)

    server = HostServer(tmp_path, bundle, auto_advance=False)
    started = threading.Event()

    def slow_recover() -> list[dict]:
        started.set()
        time.sleep(3.0)
        return []

    server.handlers.startup_recover = slow_recover  # type: ignore[method-assign]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    assert started.wait(timeout=10.0), "startup recovery thread did not start"
    deadline = time.monotonic() + 5.0
    health_ok = False
    while time.monotonic() < deadline:
        result = call_host(tmp_path, "health", timeout=2.0)
        if result.get("ok"):
            health_ok = True
            break
        time.sleep(0.1)
    server.request_stop()
    thread.join(timeout=5.0)
    assert health_ok, f"health RPC failed during startup recovery: {result}"
