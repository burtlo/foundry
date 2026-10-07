"""Unit tests for host path selection and ownership."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from foundry_cli.host.discovery import (
    HostDiscoveryError,
    acquire_host_ownership,
    host_is_running,
    read_state,
    release_host_ownership,
)
from foundry_cli.host.paths import (
    host_dir,
    runtime_socket_dir,
    socket_path,
    state_path,
    startup_log_path,
    unix_socket_path_limit,
    workspace_identity_hash,
    workspace_socket_path,
)
from foundry_cli.host.server import HostServer
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    return workspace


def test_workspace_identity_hash_is_stable(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    first = workspace_identity_hash(workspace)
    second = workspace_identity_hash(workspace)
    assert first == second
    assert len(first) == 16


def test_socket_path_uses_host_dir_when_short(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    local = workspace_socket_path(workspace.resolve())
    if len(os.fsencode(str(local))) > unix_socket_path_limit():
        pytest.skip("pytest temp dir too long for workspace-local socket on this platform")
    resolved = socket_path(workspace)
    assert resolved == local


@pytest.mark.skipif(sys.platform == "win32", reason="Unix socket path selection")
def test_socket_path_uses_runtime_when_path_too_long(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("foundry_cli.host.paths.unix_socket_path_limit", lambda: 40)
    workspace = tmp_path / ("nested" * 20) / "app"
    workspace.mkdir(parents=True)
    resolved = socket_path(workspace)
    assert resolved.parent == runtime_socket_dir()
    assert resolved.name == f"foundry-host-{workspace_identity_hash(workspace)}.sock"
    assert len(resolved.name) < unix_socket_path_limit()


@pytest.mark.skipif(sys.platform == "win32", reason="Unix socket ownership")
def test_acquire_host_ownership_blocks_second_holder(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    first = acquire_host_ownership(workspace)
    try:
        with pytest.raises(HostDiscoveryError) as exc:
            acquire_host_ownership(workspace)
        assert exc.value.code == "HOST_OWNERSHIP_CONFLICT"
    finally:
        release_host_ownership(first)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix socket bind")
def test_host_server_holds_ownership_until_stop(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    bundle = FOUNDRY_ROOT
    server = HostServer(workspace, bundle)
    ready = threading.Event()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            ready.set()
            server.serve_forever()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    ready.wait(timeout=2)
    time.sleep(0.2)
    assert host_is_running(workspace)
    with pytest.raises(HostDiscoveryError):
        acquire_host_ownership(workspace)
    server.request_stop()
    thread.join(timeout=5)
    assert not errors


def test_long_workspace_path_integration(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("Unix long-path socket bind")
    deep = tmp_path
    for index in range(24):
        deep = deep / f"segment-{index}"
    workspace = deep / "app"
    workspace.mkdir(parents=True)
    shutil.copytree(
        FOUNDRY_ROOT / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    resolved = socket_path(workspace)
    assert resolved.parent == runtime_socket_dir()
    assert not str(resolved).startswith(str(host_dir(workspace)))

    host_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "foundry_cli.host",
            "--workspace",
            str(workspace),
            "--registry",
            str(FOUNDRY_ROOT),
        ],
        cwd=str(FOUNDRY_ROOT / "cli"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        for _ in range(50):
            if host_is_running(workspace):
                break
            time.sleep(0.1)
        assert host_is_running(workspace)
        assert state_path(workspace).is_file()
        state = read_state(workspace)
        assert state is not None
        assert state.get("address") == str(resolved)
        second = subprocess.run(
            [
                sys.executable,
                "-m",
                "foundry_cli.host",
                "--workspace",
                str(workspace),
                "--registry",
                str(FOUNDRY_ROOT),
            ],
            cwd=str(FOUNDRY_ROOT / "cli"),
            capture_output=True,
            text=True,
            check=False,
        )
        assert second.returncode != 0
        assert "HOST_ALREADY_RUNNING" in second.stderr or "HOST_OWNERSHIP" in second.stderr
    finally:
        if host_is_running(workspace):
            from foundry_cli.host.client import call_host

            call_host(workspace, "host.stop", {"idempotency_key": "test-stop"})
        host_proc.wait(timeout=15)


def test_append_startup_log_writes_under_host_dir(tmp_path: Path) -> None:
    from foundry_cli.host.discovery import append_startup_log

    workspace = tmp_path / "app"
    workspace.mkdir()
    append_startup_log(workspace, "BIND_FAILED test message")
    log = startup_log_path(workspace)
    assert log.is_file()
    assert "BIND_FAILED test message" in log.read_text(encoding="utf-8")
