"""Workspace-local paths for the Foundry job host."""

from __future__ import annotations

from pathlib import Path

HOST_DIR_NAME = "host"
STATE_FILE_NAME = "state.json"
LOCK_FILE_NAME = "host.lock"
SOCKET_FILE_NAME = "socket"

PROTOCOL_VERSION = 1


def host_dir(workspace: Path) -> Path:
    return workspace.resolve() / ".foundry" / HOST_DIR_NAME


def state_path(workspace: Path) -> Path:
    return host_dir(workspace) / STATE_FILE_NAME


def lock_path(workspace: Path) -> Path:
    return host_dir(workspace) / LOCK_FILE_NAME


def socket_path(workspace: Path) -> Path:
    return host_dir(workspace) / SOCKET_FILE_NAME
