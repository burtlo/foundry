"""Snapshot state patch enforcement."""

from __future__ import annotations

from typing import Any

from foundry_cli.state_paths import is_patch_key_allowed


def patch_allowed(
    snapshot: dict[str, Any],
    node: dict[str, Any],
    node_id: str,
    patch: dict[str, Any],
) -> tuple[list[str], list[str]]:
    allow = node.get("allow") or {}
    state = snapshot.setdefault("state", {})
    if not isinstance(state, dict):
        state = {}
        snapshot["state"] = state
    patched: list[str] = []
    rejected: list[str] = []
    for key, value in patch.items():
        key_str = str(key)
        if is_patch_key_allowed(key_str, allow, node_id):
            state[key_str] = value
            patched.append(key_str)
        else:
            rejected.append(key_str)
    return patched, rejected
