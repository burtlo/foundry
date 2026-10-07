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
from foundry_cli.engine.execute_step_executor import EXECUTE_BRANCH_NODE
from foundry_cli.engine.gate_rules import has_gate_rules
from foundry_cli.engine.verify_step_executor import DELIVER_STUB_NODE
from foundry_cli.registry import get_node

DELIVER_STUB_NODE_ID = DELIVER_STUB_NODE

_BLOCKED_INTAKE_NODE_IDS: frozenset[str] = frozenset(
    {
        "execute.intake",
        "verify.intake",
    }
)

_HOST_ONLY_BOUNDARY_NODE_IDS: frozenset[str] = frozenset(
    {
        "execute.intake",
        "verify.intake",
        "execute.test",
    }
)

GIT_MECHANICAL_STEP_NODE_IDS: tuple[str, ...] = (EXECUTE_BRANCH_NODE,)

_HOST_IMPLEMENTED_STEP_NODES: frozenset[str] = frozenset(
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
        DELIVER_STUB_NODE_ID,
    }
)

_SHAPE_JUDGMENT_STEP_NODE_IDS: frozenset[str] = frozenset(
    {
        "shape.examine",
        "shape.present",
        "shape.record",
    }
)


def is_post_shape_flow_node(node_id: str) -> bool:
    if node_id == DELIVER_STUB_NODE_ID:
        return True
    return node_id.startswith("execute.") or node_id.startswith("verify.")


class AdvanceMode(str, Enum):
    """How the host advances an opened visit at this node."""

    HOST = "host"
    TASK = "task"
    GIT_MECHANICAL = "git_mechanical"
    GATE_USER = "gate_user"
    GATE_ENGINE = "gate_engine"
    MANUAL = "manual"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class NodeRuntimeProfile:
    node_id: str
    advance_mode: AdvanceMode
    operations_ref: str | None
    task_id: str | None
    blocked_intake: bool
    host_only_boundary: bool
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


def resolve_advance_mode(
    node_id: str,
    flow: dict[str, Any],
    foundry_bundle: Path | None = None,
) -> AdvanceMode:
    """Resolve advance mode using the same ordering as legacy classification."""
    kind = _node_kind(node_id, flow)
    if kind == "gate":
        if _gate_decider(node_id, flow) == "user":
            return AdvanceMode.GATE_USER
        return AdvanceMode.GATE_ENGINE
    if node_id in GIT_MECHANICAL_STEP_NODE_IDS:
        return AdvanceMode.GIT_MECHANICAL
    if node_id in _HOST_IMPLEMENTED_STEP_NODES:
        return AdvanceMode.HOST
    if foundry_bundle is not None and task_registry_binding_exists(
        node_id, foundry_bundle
    ):
        return AdvanceMode.TASK
    if is_post_shape_flow_node(node_id):
        return AdvanceMode.UNSUPPORTED
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
    return NodeRuntimeProfile(
        node_id=node_id,
        advance_mode=advance_mode,
        operations_ref=_operations_ref(
            node,
            node_id,
            foundry_bundle,
            operations_file_exists=operations_file_exists,
        ),
        task_id=_task_id_for_mode(node_id, advance_mode),
        blocked_intake=node_id in _BLOCKED_INTAKE_NODE_IDS,
        host_only_boundary=node_id in _HOST_ONLY_BOUNDARY_NODE_IDS,
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
