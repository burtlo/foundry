"""Declarative node runtime profile (engine DSL Step 1–2).

Loads how a flow node is advanced from registry node.yaml and bundle
filesystem (tasks/, nodes/*/operations.yaml). Classification is centralized
here; ``classify_advance_node`` and ``node_capability.boundary_status`` delegate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from foundry_cli.engine.agent.tasks import task_registry_binding_exists
from foundry_cli.engine.gate_rules import has_gate_rules
from foundry_cli.node_operations import load_operations
from foundry_cli.registry import get_node

RUNTIME_PROFILE_ALLOWED_KEYS = frozenset(
    {
        "advance",
        "blocked_intake",
        "host_only_boundary",
        "requires_work_prompt",
        "pending_open_questions",
        "terminal",
    }
)

# Stable id for tests and capability audit labels (advance mode comes from node runtime).
GIT_MECHANICAL_STEP_NODE_IDS: tuple[str, ...] = ("execute.branch",)


class AdvanceMode(str, Enum):
    """How the host advances an opened visit at this node."""

    HOST = "host"
    TASK = "task"
    GIT_MECHANICAL = "git_mechanical"
    GATE_USER = "gate_user"
    GATE_ENGINE = "gate_engine"
    MANUAL = "manual"
    UNSUPPORTED = "unsupported"


_RUNTIME_ADVANCE_TO_MODE: dict[str, AdvanceMode] = {
    "host": AdvanceMode.HOST,
    "task": AdvanceMode.TASK,
    "git_mechanical": AdvanceMode.GIT_MECHANICAL,
    "manual": AdvanceMode.MANUAL,
}


@dataclass(frozen=True)
class NodeRuntimeProfile:
    node_id: str
    advance_mode: AdvanceMode
    operations_ref: str | None
    task_id: str | None
    blocked_intake: bool
    host_only_boundary: bool
    requires_work_prompt: bool
    terminal: bool
    pending_open_questions: bool
    work_prompt_wait_summary: str | None
    work_prompt_request_ref: str | None
    engine_gate_resolver: str | None
    task_file_exists: bool
    operations_file_exists: bool


def _node_kind(node_id: str, flow: dict[str, Any]) -> str:
    try:
        node = get_node(flow, node_id)
    except KeyError:
        return ""
    return str(node.get("kind") or "")


def _gate_decider(node_id: str, flow: dict[str, Any]) -> str:
    try:
        node = get_node(flow, node_id)
    except KeyError:
        return ""
    return str(node.get("decider") or "")


def _runtime_dict(node: dict[str, Any]) -> dict[str, Any]:
    runtime = node.get("runtime")
    return runtime if isinstance(runtime, dict) else {}


def _runtime_advance(node: dict[str, Any]) -> str | None:
    raw = _runtime_dict(node).get("advance")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _runtime_bool(node: dict[str, Any], key: str) -> bool:
    value = _runtime_dict(node).get(key)
    return value is True


def resolve_advance_mode(
    node_id: str,
    flow: dict[str, Any],
    foundry_bundle: Path | None = None,
) -> AdvanceMode:
    """Resolve advance mode from flow node runtime and bundle layout."""
    kind = _node_kind(node_id, flow)
    if kind == "gate":
        if _gate_decider(node_id, flow) == "user":
            return AdvanceMode.GATE_USER
        return AdvanceMode.GATE_ENGINE
    if kind != "step":
        return AdvanceMode.UNSUPPORTED

    try:
        node = get_node(flow, node_id)
    except KeyError:
        return AdvanceMode.UNSUPPORTED

    advance = _runtime_advance(node)
    if advance is not None:
        mode = _RUNTIME_ADVANCE_TO_MODE.get(advance)
        if mode is not None:
            return mode
        return AdvanceMode.UNSUPPORTED

    if foundry_bundle is not None and task_registry_binding_exists(
        node_id, foundry_bundle
    ):
        return AdvanceMode.TASK
    return AdvanceMode.UNSUPPORTED


def _operations_ref(
    node: dict[str, Any],
    node_id: str,
    foundry_bundle: Path,
    *,
    operations_file_exists: bool,
) -> str | None:
    operations = node.get("operations")
    if isinstance(operations, str) and operations.strip():
        return operations.strip()
    if operations_file_exists:
        return f"registry:nodes/{node_id}/operations.yaml"
    return None


def _task_id_for_mode(node_id: str, mode: AdvanceMode) -> str | None:
    if mode == AdvanceMode.TASK:
        return node_id
    return None


def _work_prompt_wait_from_operations(
    operations_ref: str | None,
    foundry_bundle: Path,
) -> tuple[str | None, str | None]:
    if not operations_ref:
        return None, None
    try:
        operations = load_operations(operations_ref, foundry_bundle)
    except (KeyError, ValueError, OSError):
        return None, None
    presentation = operations.get("presentation")
    if not isinstance(presentation, dict):
        return None, None
    wait = presentation.get("work_prompt_wait")
    if not isinstance(wait, dict):
        return None, None
    summary = wait.get("summary")
    request_ref = wait.get("request_ref")
    summary_out = str(summary).strip() if isinstance(summary, str) and summary.strip() else None
    ref_out = (
        str(request_ref).strip()
        if isinstance(request_ref, str) and request_ref.strip()
        else None
    )
    return summary_out, ref_out


def _engine_gate_resolver_id(node_id: str, mode: AdvanceMode, foundry_bundle: Path) -> str | None:
    if mode != AdvanceMode.GATE_ENGINE:
        return None
    if has_gate_rules(node_id, foundry_bundle):
        return node_id
    return None


def load_node_runtime_profile(
    node_id: str,
    flow: dict[str, Any],
    foundry_bundle: Path,
) -> NodeRuntimeProfile:
    """Load runtime profile for ``node_id`` from flow registry and bundle layout."""
    node = get_node(flow, node_id)
    task_path = foundry_bundle / "tasks" / f"{node_id}.yaml"
    ops_path = foundry_bundle / "nodes" / node_id / "operations.yaml"
    task_file_exists = task_path.is_file()
    operations_file_exists = ops_path.is_file()
    advance_mode = resolve_advance_mode(node_id, flow, foundry_bundle)
    operations_ref = _operations_ref(
        node,
        node_id,
        foundry_bundle,
        operations_file_exists=operations_file_exists,
    )
    wait_summary, wait_request_ref = _work_prompt_wait_from_operations(
        operations_ref,
        foundry_bundle,
    )
    return NodeRuntimeProfile(
        node_id=node_id,
        advance_mode=advance_mode,
        operations_ref=operations_ref,
        task_id=_task_id_for_mode(node_id, advance_mode),
        blocked_intake=_runtime_bool(node, "blocked_intake"),
        host_only_boundary=_runtime_bool(node, "host_only_boundary"),
        requires_work_prompt=_runtime_bool(node, "requires_work_prompt"),
        terminal=bool(node.get("terminal")) or _runtime_bool(node, "terminal"),
        pending_open_questions=_runtime_bool(node, "pending_open_questions"),
        work_prompt_wait_summary=wait_summary,
        work_prompt_request_ref=wait_request_ref,
        engine_gate_resolver=_engine_gate_resolver_id(node_id, advance_mode, foundry_bundle),
        task_file_exists=task_file_exists,
        operations_file_exists=operations_file_exists,
    )


def advance_mode_for_classifier_parity(advance_mode: AdvanceMode) -> str:
    """Map profile mode to ``AdvanceNodeClass.value`` for parity tests."""
    from foundry_cli.engine.advance_classifier import AdvanceNodeClass

    return {
        AdvanceMode.HOST: AdvanceNodeClass.HOST_STEP.value,
        AdvanceMode.TASK: AdvanceNodeClass.TASK_BOUND_STEP.value,
        AdvanceMode.GIT_MECHANICAL: AdvanceNodeClass.GIT_MECHANICAL_STEP.value,
        AdvanceMode.GATE_USER: AdvanceNodeClass.USER_GATE.value,
        AdvanceMode.GATE_ENGINE: AdvanceNodeClass.ENGINE_GATE.value,
        AdvanceMode.UNSUPPORTED: AdvanceNodeClass.UNSUPPORTED.value,
        AdvanceMode.MANUAL: AdvanceNodeClass.UNSUPPORTED.value,
    }[advance_mode]


def advance_node_class_from_mode(advance_mode: AdvanceMode) -> Any:
    """Map ``AdvanceMode`` to ``AdvanceNodeClass`` (lazy import avoids cycles)."""
    from foundry_cli.engine.advance_classifier import AdvanceNodeClass

    return {
        AdvanceMode.HOST: AdvanceNodeClass.HOST_STEP,
        AdvanceMode.TASK: AdvanceNodeClass.TASK_BOUND_STEP,
        AdvanceMode.GIT_MECHANICAL: AdvanceNodeClass.GIT_MECHANICAL_STEP,
        AdvanceMode.GATE_USER: AdvanceNodeClass.USER_GATE,
        AdvanceMode.GATE_ENGINE: AdvanceNodeClass.ENGINE_GATE,
        AdvanceMode.UNSUPPORTED: AdvanceNodeClass.UNSUPPORTED,
        AdvanceMode.MANUAL: AdvanceNodeClass.UNSUPPORTED,
    }[advance_mode]
