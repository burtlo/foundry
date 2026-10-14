"""P4 hardening: ``foundry up`` idempotency with in-thread mock bridge."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from foundry_cli.bridge.discovery import read_state as read_bridge_state
from foundry_cli.constants import OPERATOR_SMOKE_BRIDGE_URL_ENV
from foundry_cli.operator_integration_smoke import (
    _integration_workspace,
    _run_cli,
    _start_bridge,
)
from tests.conftest import FOUNDRY_ROOT

pytestmark = pytest.mark.xdist_group(name="foundry_up_hardening")

BUNDLE = FOUNDRY_ROOT


def _judgment_bridge_pids() -> set[int]:
    """PIDs of detached ``python -m foundry_cli.judgment_bridge`` processes (best-effort)."""
    if sys.platform == "win32":
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='python3.exe'\" "
                "| Where-Object { $_.CommandLine -match 'foundry_cli\\.judgment_bridge' } "
                "| Select-Object -ExpandProperty ProcessId"
            ),
        ]
    else:
        cmd = ["pgrep", "-f", "foundry_cli.judgment_bridge"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError:
        return set()
    pids: set[int] = set()
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.isdigit():
            pids.add(int(line))
    return pids


def _host_pid(cli_path: Path, workspace: Path, bundle: Path) -> int:
    status = _run_cli(cli_path, workspace, bundle, "host", "status")
    assert status.returncode == 0, status.stderr or status.stdout
    body = json.loads(status.stdout)
    process = body.get("process") if isinstance(body.get("process"), dict) else {}
    pid = int(process.get("pid") or body.get("pid") or 0)
    assert pid > 0, body
    return pid


def test_foundry_up_idempotent_with_mock_bridge() -> None:
    cli_path = BUNDLE / "cli" / "foundry.py"
    bridge_before = _judgment_bridge_pids()
    temp_dir = tempfile.TemporaryDirectory(prefix="foundry-up-hardening-")
    workspace = _integration_workspace(Path(temp_dir.name), BUNDLE)
    bridge_server = None
    try:
        bridge_server, _thread, bridge_url = _start_bridge(
            workspace,
            BUNDLE,
            mock_judgment=True,
        )
        up_env = {OPERATOR_SMOKE_BRIDGE_URL_ENV: bridge_url}

        first = _run_cli(cli_path, workspace, BUNDLE, "up", extra_env=up_env)
        assert first.returncode == 0, first.stderr or first.stdout
        first_body = json.loads(first.stdout)
        assert first_body.get("ok") is True
        assert first_body.get("ready") is True
        assert read_bridge_state(workspace) is None

        host_pid_after_first = _host_pid(cli_path, workspace, BUNDLE)

        second = _run_cli(cli_path, workspace, BUNDLE, "up", extra_env=up_env)
        assert second.returncode == 0, second.stderr or second.stdout
        second_body = json.loads(second.stdout)
        assert second_body.get("ok") is True
        assert second_body.get("ready") is True

        bridge = second_body.get("bridge") if isinstance(second_body.get("bridge"), dict) else {}
        assert bridge.get("already_running") is True

        host_pid_after_second = _host_pid(cli_path, workspace, BUNDLE)
        assert host_pid_after_second == host_pid_after_first

        bridge_after = _judgment_bridge_pids()
        assert bridge_after == bridge_before
    finally:
        stop = _run_cli(cli_path, workspace, BUNDLE, "host", "stop")
        if stop.returncode != 0:
            pass
        if bridge_server is not None:
            bridge_server.shutdown()
        temp_dir.cleanup()
