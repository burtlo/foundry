"""Thin compatibility facade for advance-node classification."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from foundry_cli.engine.agent.tasks import (
    EXECUTE_PLAN_TASK_ID,
    SHAPE_EXAMINE_TASK_ID,
    SHAPE_PRESENT_TASK_ID,
    SHAPE_RECORD_TASK_ID,
    VERIFY_ACCEPTANCE_TASK_ID,
)
from foundry_cli.engine.node_runtime_profile import (
    GIT_MECHANICAL_STEP_NODE_IDS,
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


TASK_BOUND_STEP_NODE_IDS: tuple[str, ...] = (
    SHAPE_EXAMINE_TASK_ID,
    SHAPE_PRESENT_TASK_ID,
    SHAPE_RECORD_TASK_ID,
    EXECUTE_PLAN_TASK_ID,
    VERIFY_ACCEPTANCE_TASK_ID,
)

_HOST_ADVANCE: frozenset[str] = frozenset(
    {
        "shape.intake",
        "execute.intake",
        "execute.build",
        "execute.test",
        "execute.commit",
        "verify.intake",
        "verify.code_quality",
        "verify.code_review",
        "verify.complete",
        "deliver.stub",
    }
)
_HOST_BOUNDARY_WAIT: frozenset[str] = frozenset({"shape.intake"})
_TASK_BOUND_ADVANCE: frozenset[str] = frozenset(TASK_BOUND_STEP_NODE_IDS)
_TASK_BOUND_BOUNDARY_WAIT: frozenset[str] = frozenset(TASK_BOUND_STEP_NODE_IDS)
_GIT_MECHANICAL_ADVANCE: frozenset[str] = frozenset(GIT_MECHANICAL_STEP_NODE_IDS)


def classify_advance_node(
    node_id: str,
    flow: dict[str, Any],
    *,
    foundry_bundle: Path | None = None,
) -> AdvanceNodeClass:
    """Classify how advancement should treat this node."""
    mode = resolve_advance_mode(node_id, flow, foundry_bundle)
    return advance_node_class_from_mode(mode)


def _work_prompt_from_snapshot(snapshot: dict[str, Any]) -> str | None:
    config = snapshot.get("config")
    if isinstance(config, dict):
        shape = config.get("shape")
        if isinstance(shape, dict):
            prompt = shape.get("work_prompt")
            if isinstance(prompt, str) and prompt.strip():
                return prompt
        direct = config.get("work_prompt")
        if isinstance(direct, str) and direct.strip():
            return direct
    state = snapshot.get("state")
    if isinstance(state, dict):
        prompt = state.get("work_prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt
    return None
