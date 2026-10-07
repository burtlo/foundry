"""Workspace-local paths for the Foundry job host."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

HOST_DIR_NAME = "host"
STATE_FILE_NAME = "state.json"
LOCK_FILE_NAME = "host.lock"
SPAWN_LOCK_FILE_NAME = "spawn.lock"
SOCKET_FILE_NAME = "socket"
STARTUP_LOG_FILE_NAME = "startup.log"
HOST_LOG_FILE_NAME = "host.log"
AUTO_ADVANCE_STATUS_FILE_NAME = "auto_advance.json"

PROTOCOL_VERSION = 1


def host_dir(workspace: Path) -> Path:
    return workspace.resolve() / ".foundry" / HOST_DIR_NAME


def state_path(workspace: Path) -> Path:
    return host_dir(workspace) / STATE_FILE_NAME


def lock_path(workspace: Path) -> Path:
    return host_dir(workspace) / LOCK_FILE_NAME


def spawn_lock_path(workspace: Path) -> Path:
    return host_dir(workspace) / SPAWN_LOCK_FILE_NAME


def startup_log_path(workspace: Path) -> Path:
    return host_dir(workspace) / STARTUP_LOG_FILE_NAME


def host_log_path(workspace: Path) -> Path:
    return host_dir(workspace) / HOST_LOG_FILE_NAME


def auto_advance_status_path(workspace: Path) -> Path:
    return host_dir(workspace) / AUTO_ADVANCE_STATUS_FILE_NAME


def workspace_socket_path(workspace: Path) -> Path:
    """Default Unix socket location under the workspace host directory."""
    return host_dir(workspace) / SOCKET_FILE_NAME


def unix_socket_path_limit() -> int:
    """Maximum length of a Unix socket path on this platform."""
    if sys.platform == "darwin":
        return 104
    return 108


def workspace_identity_hash(workspace: Path) -> str:
    canonical = str(workspace.resolve())
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:16]


def runtime_socket_dir() -> Path:
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        return Path(xdg)
    return Path(tempfile.gettempdir())


def socket_path(workspace: Path) -> Path:
    """Resolve the Unix socket bind path for a workspace.

    Uses a short runtime path keyed by workspace identity when the workspace-local
    path would exceed platform limits. Windows callers use TCP instead.
    """
    ws = workspace.resolve()
    local = workspace_socket_path(ws)
    if sys.platform == "win32":
        return local
    if len(os.fsencode(str(local))) <= unix_socket_path_limit():
        return local
    identity = workspace_identity_hash(ws)
    return runtime_socket_dir() / f"foundry-host-{identity}.sock"
