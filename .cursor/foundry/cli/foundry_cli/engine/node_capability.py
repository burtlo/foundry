"""Execute / Verify / Deliver advancement capabilities (workflow-02 boundary)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from foundry_cli.engine.agent.tasks import (
    EXECUTE_PLAN_TASK_ID,
    SHAPE_EXAMINE_TASK_ID,
    SHAPE_PRESENT_TASK_ID,
    SHAPE_RECORD_TASK_ID,
    VERIFY_ACCEPTANCE_TASK_ID,
)
from foundry_cli.engine.node_runtime_profile import (
    GIT_MECHANICAL_STEP_NODE_IDS,
    AdvanceMode,
    resolve_advance_mode,
)

_SHAPE_JUDGMENT_STEP_NODE_IDS: frozenset[str] = frozenset(
    {
        SHAPE_EXAMINE_TASK_ID,
        SHAPE_PRESENT_TASK_ID,
        SHAPE_RECORD_TASK_ID,
    }
)
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


def _node_kind(node_id: str, flow: dict[str, Any]) -> str:
    try:
        node = get_node(flow, node_id)
    except KeyError:
        return ""
    return str(node.get("kind") or "")


def _boundary_status_from_mode(
    mode: AdvanceMode,
    node_id: str,
    *,
    foundry_bundle: Path | None,
) -> BoundaryStatus:
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
    if (
        foundry_bundle is None
        and node_id in _SHAPE_JUDGMENT_STEP_NODE_IDS
    ):
        return "implemented"
    return "unsupported"


def boundary_status(
    node_id: str,
    flow: dict[str, Any],
    *,
    foundry_bundle: Path | None = None,
) -> BoundaryStatus:
    """Classify how the host advances at this node today."""
    mode = resolve_advance_mode(node_id, flow, foundry_bundle)
    return _boundary_status_from_mode(
        mode,
        node_id,
        foundry_bundle=foundry_bundle,
    )


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
    """Rows for docs/features/execute-verify-boundary-audit.md."""
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
        if node_id in GIT_MECHANICAL_STEP_NODE_IDS:
            return "Git/mechanical advance class (`run_execute_branch_complete`)"
        if node_id == EXECUTE_PLAN_TASK_ID:
            return (
                "Agent task binding (`execute.plan`); "
                "`dispatch_task_bound_advance` after submit"
            )
        if node_id == VERIFY_ACCEPTANCE_TASK_ID:
            return (
                "Agent task binding (`verify.acceptance`); "
                "`dispatch_task_bound_advance` after submit"
            )
        if node_id in _SHAPE_JUDGMENT_STEP_NODE_IDS:
            return (
                f"Agent task binding (`{node_id}`); "
                "`shape_step_executor` completer after submit"
            )
        return "Host-owned step executor or task binding"
    if status == "gate-user":
        if node_id == "execute.start":
            return "Decision wait; `foundry start` records authorization and accepts gate"
        return "Decision wait; user `gate decide` / `decide`"
    if status == "gate-engine":
        from foundry_cli.engine.gate_rules import has_gate_rules

        if has_gate_rules(node_id):
            return (
                "Engine gate; `resolve_engine_gate` on advance "
                "(host routes after decision)"
            )
        return "Engine gate (checks only; no resolver on advance yet)"
    return f"Operator wait with request_ref unsupported:{node_id}"
