"""Host discovery: pid, endpoint, and single-host lock."""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from foundry_cli.host.paths import (
    LOCK_FILE_NAME,
    PROTOCOL_VERSION,
    host_dir,
    lock_path,
    spawn_lock_path,
    startup_log_path,
    state_path,
)
from foundry_cli.util import now_iso


class HostDiscoveryError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _lock_file(handle, *, nonblocking: bool = False) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        mode = msvcrt.LK_NBLCK if nonblocking else msvcrt.LK_LOCK
        try:
            msvcrt.locking(handle.fileno(), mode, 1)
        except OSError as exc:
            if nonblocking:
                raise BlockingIOError from exc
            raise
        return
    import fcntl

    flags = fcntl.LOCK_EX
    if nonblocking:
        flags |= fcntl.LOCK_NB
    fcntl.flock(handle.fileno(), flags)


def _unlock_file(handle) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def restrict_host_dir_permissions(directory: Path) -> None:
    """Best-effort owner-only access on host metadata directory."""
    directory.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        return
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass


def write_state(
    workspace: Path,
    *,
    pid: int,
    transport: str,
    address: str,
    port: int | None = None,
    auto_advance: bool = False,
    auto_advance_interval: float | None = None,
) -> Path:
    restrict_host_dir_permissions(host_dir(workspace))
    payload: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "pid": pid,
        "transport": transport,
        "address": address,
        "started_at": now_iso(),
    }
    if port is not None:
        payload["port"] = port
    payload["auto_advance"] = bool(auto_advance)
    if auto_advance_interval is not None:
        payload["auto_advance_interval"] = float(auto_advance_interval)
    path = state_path(workspace)
    temp = path.with_suffix(".json.tmp")
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with temp.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    if sys.platform != "win32":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path


def read_state(workspace: Path) -> dict[str, Any] | None:
    path = state_path(workspace)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return None
    return data


def clear_state(workspace: Path) -> None:
    path = state_path(workspace)
    if path.is_file():
        path.unlink()


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def host_is_running(workspace: Path) -> bool:
    state = read_state(workspace)
    if not state:
        return False
    pid = int(state.get("pid") or 0)
    return pid_alive(pid)


def append_startup_log(workspace: Path, message: str) -> None:
    """Append a line to the workspace host startup log (bind / ownership errors)."""
    directory = host_dir(workspace)
    restrict_host_dir_permissions(directory)
    path = startup_log_path(workspace)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{now_iso()} {message}\n")


def acquire_host_ownership(workspace: Path):
    """Acquire exclusive host ownership for the process lifetime.

    Returns an open lock file handle that must stay open until ``release_host_ownership``.
    """
    directory = host_dir(workspace)
    restrict_host_dir_permissions(directory)
    lock_file = lock_path(workspace)
    handle = lock_file.open("a+b")
    try:
        _lock_file(handle, nonblocking=True)
    except BlockingIOError:
        handle.close()
        if host_is_running(workspace):
            raise HostDiscoveryError(
                "HOST_ALREADY_RUNNING",
                "Another Foundry host is already running for this workspace",
            ) from None
        raise HostDiscoveryError(
            "HOST_OWNERSHIP_CONFLICT",
            "Could not acquire host ownership; another host may be starting",
        ) from None
    except OSError as exc:
        handle.close()
        raise HostDiscoveryError("HOST_OWNERSHIP_FAILED", str(exc)) from exc
    return handle


def release_host_ownership(handle) -> None:
    try:
        _unlock_file(handle)
    finally:
        handle.close()


@contextmanager
def host_startup_lock(workspace: Path) -> Iterator[None]:
    """Brief lock while the CLI spawns a detached host (does not block a running host)."""
    directory = host_dir(workspace)
    restrict_host_dir_permissions(directory)
    lock_file = spawn_lock_path(workspace)
    with lock_file.open("a+b") as handle:
        _lock_file(handle, nonblocking=False)
        try:
            yield
        finally:
            _unlock_file(handle)
