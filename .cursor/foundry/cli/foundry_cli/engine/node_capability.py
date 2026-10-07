"""Execute / Verify / Deliver advancement boundary helpers (unsupported waits)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from foundry_cli.engine.node_runtime_profile import AdvanceMode, resolve_advance_mode
from foundry_cli.registry import get_node

BoundaryStatus = Literal[
    "implemented",
    "gate-user",
    "gate-engine",
    "unsupported",
]

UNSUPPORTED_REQUEST_REF_PREFIX = "unsupported:"
DELIVER_STUB_NODE_ID = "deliver.stub"


def _node_kind(node_id: str, flow: dict[str, Any]) -> str:
    try:
        node = get_node(flow, node_id)
    except KeyError:
        return ""
    return str(node.get("kind") or "")


def _boundary_status_from_mode(mode: AdvanceMode) -> BoundaryStatus:
    if mode in (
        AdvanceMode.HOST,
        AdvanceMode.TASK,
        AdvanceMode.GIT_MECHANICAL,
    ):
        return "implemented"
    if mode == AdvanceMode.GATE_USER:
        return "gate-user"
    if mode == AdvanceMode.GATE_ENGINE:
        return "gate-engine"
    return "unsupported"


def boundary_status(
    node_id: str,
    flow: dict[str, Any],
    *,
    foundry_bundle: Path | None = None,
) -> BoundaryStatus:
    """Classify how the host advances at this node today."""
    mode = resolve_advance_mode(node_id, flow, foundry_bundle)
    return _boundary_status_from_mode(mode)


def should_emit_unsupported_operator_wait(
    node_id: str,
    flow: dict[str, Any],
    *,
    foundry_bundle: Path,
) -> bool:
    """True when advancement must stop with an explicit unsupported-node operator wait."""
    if boundary_status(node_id, flow, foundry_bundle=foundry_bundle) != "unsupported":
        return False
    return _node_kind(node_id, flow) == "step"


def unsupported_request_ref(node_id: str) -> str:
    return f"{UNSUPPORTED_REQUEST_REF_PREFIX}{node_id}"


def unsupported_wait_summary(node_id: str) -> str:
    return (
        f"{node_id} is not yet implemented in the Foundry host engine "
        "(Execute/Verify automation is planned for workflow-02)."
    )
