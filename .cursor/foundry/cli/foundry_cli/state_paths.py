"""Canonical state-path grants for context display and patch enforcement."""

from __future__ import annotations

from typing import Any


def node_scope_prefix(node_id: str) -> str:
    """Canonical prefix for node-scoped patch keys within snapshot state."""
    return f"nodes.{node_id}."


def implicit_state_grant(node_id: str) -> str:
    """Wildcard grant shown in context packets (full logical path under snapshot state)."""
    return f"state.nodes.{node_id}.*"


def _explicit_state_keys(allow: dict[str, Any]) -> set[str]:
    return {str(item) for item in (allow.get("state") or [])}


def is_patch_key_allowed(key: str, allow: dict[str, Any], node_id: str) -> bool:
    key_str = str(key)
    if key_str in _explicit_state_keys(allow):
        return True
    return key_str.startswith(node_scope_prefix(node_id))


def patch_allowed_keys(allow: dict[str, Any], node_id: str, patch: dict[str, Any]) -> tuple[bool, str | None]:
    rejected = [str(key) for key in patch if not is_patch_key_allowed(str(key), allow, node_id)]
    if rejected:
        return False, f"Rejected paths: {', '.join(rejected)}"
    return True, None


def effective_state_grants(allow: dict[str, Any], node_id: str) -> list[str]:
    """Merge explicit allow.state entries with the implicit node-scope grant."""
    state = [str(item) for item in (allow.get("state") or [])]
    implicit = implicit_state_grant(node_id)
    if implicit not in state:
        state.append(implicit)
    return state
