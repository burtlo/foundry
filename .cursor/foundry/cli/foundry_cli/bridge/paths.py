"""Workspace-local paths for the judgment bridge."""

from __future__ import annotations

from pathlib import Path

BRIDGE_DIR_NAME = "bridge"
STATE_FILE_NAME = "state.json"
LOG_FILE_NAME = "bridge.log"
SPAWN_LOCK_FILE_NAME = "spawn.lock"

DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 8791


def bridge_dir(workspace: Path) -> Path:
    return workspace.resolve() / ".foundry" / BRIDGE_DIR_NAME


def state_path(workspace: Path) -> Path:
    return bridge_dir(workspace) / STATE_FILE_NAME


def log_path(workspace: Path) -> Path:
    return bridge_dir(workspace) / LOG_FILE_NAME


def spawn_lock_path(workspace: Path) -> Path:
    return bridge_dir(workspace) / SPAWN_LOCK_FILE_NAME
