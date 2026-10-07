"""Thin compatibility facade for advance-node classification."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from foundry_cli.engine.node_runtime_profile import (
    advance_node_class_from_mode,
    resolve_advance_mode,
)


class AdvanceNodeClass(str, Enum):
    USER_GATE = "user_gate"
    ENGINE_GATE = "engine_gate"
    TASK_BOUND_STEP = "task_bound_step"
    GIT_MECHANICAL_STEP = "git_mechanical_step"
    HOST_STEP = "host_step"
    UNSUPPORTED = "unsupported"


def classify_advance_node(
    node_id: str,
    flow: dict[str, Any],
    *,
    foundry_bundle: Path | None = None,
) -> AdvanceNodeClass:
    """Classify how advancement should treat this node."""
    mode = resolve_advance_mode(node_id, flow, foundry_bundle)
    return advance_node_class_from_mode(mode)
