"""Execute / Verify / Deliver advancement capabilities (workflow-02 boundary)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from foundry_cli.engine.agent.tasks import task_registry_binding_exists
from foundry_cli.registry import get_node

BoundaryStatus = Literal[
    "implemented",
    "gate-user",
    "gate-engine",
    "unsupported",
]

UNSUPPORTED_REQUEST_REF_PREFIX = "unsupported:"
DELIVER_STUB_NODE_ID = "deliver.stub"

# Ordered audit list (execute.intake through deliver.stub in flow order).
EXECUTE_VERIFY_DELIVER_NODE_IDS: tuple[str, ...] = (
    "execute.start",
    "execute.intake",
    "execute.intake.gate",
    "execute.branch",
    "execute.plan",
    "execute.build",
    "execute.test",
    "execute.test.gate",
    "execute.repair.limit.gate",
    "execute.commit",
    "execute.commit.gate",
    "verify.intake",
    "verify.intake.gate",
    "verify.acceptance",
    "verify.acceptance.gate",
    "verify.code_quality",
    "verify.code_quality.gate",
    "verify.code_review",
    "verify.code_review.gate",
    "verify.complete",
    "verify.complete.gate",
    DELIVER_STUB_NODE_ID,
)

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


def is_post_shape_flow_node(node_id: str) -> bool:
    if node_id == DELIVER_STUB_NODE_ID:
        return True
    return node_id.startswith("execute.") or node_id.startswith("verify.")


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


def boundary_status(
    node_id: str,
    flow: dict[str, Any],
    *,
    foundry_bundle: Path | None = None,
) -> BoundaryStatus:
    """Classify how the host advances at this node today."""
    from foundry_cli.engine.advance_classifier import GIT_MECHANICAL_STEP_NODE_IDS

    if node_id in GIT_MECHANICAL_STEP_NODE_IDS:
        return "implemented"
    if node_id in _HOST_IMPLEMENTED_STEP_NODES:
        return "implemented"
    kind = _node_kind(node_id, flow)
    if kind == "gate":
        if _gate_decider(node_id, flow) == "user":
            return "gate-user"
        return "gate-engine"
    if (
        foundry_bundle is not None
        and task_registry_binding_exists(node_id, foundry_bundle)
    ):
        return "implemented"
    if is_post_shape_flow_node(node_id):
        return "unsupported"
    return "unsupported"


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


def audit_rows(flow: dict[str, Any], foundry_bundle: Path) -> list[dict[str, str]]:
    """Rows for docs/plans/execute-verify-boundary-audit.md."""
    rows: list[dict[str, str]] = []
    for node_id in EXECUTE_VERIFY_DELIVER_NODE_IDS:
        status = boundary_status(node_id, flow, foundry_bundle=foundry_bundle)
        rows.append(
            {
                "node_id": node_id,
                "status": status,
                "advance_behavior": _advance_behavior_label(status, node_id),
            }
        )
    return rows


def _advance_behavior_label(status: BoundaryStatus, node_id: str) -> str:
    if status == "implemented":
        return "Host-owned step executor or task binding"
    if status == "gate-user":
        if node_id == "execute.start":
            return "Decision wait; `foundry start` records authorization and accepts gate"
        return "Decision wait; user `gate decide` / `decide`"
    if status == "gate-engine":
        return "Engine gate (checks only; no host auto-route yet)"
    return "Operator wait with request_ref unsupported:{node_id}"
