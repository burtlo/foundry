"""Blocked execute/verify intake operator wait and recovery (G5 / REL-011)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.constants import LIFECYCLE_OPENED
from foundry_cli.engine.intake_executor import INTAKE_RECEIPT_SCHEMA
from foundry_cli.engine.node_runtime_profile import load_node_runtime_profile
from foundry_cli.engine.run_status_reason import clear_status_reason, set_status_reason
from foundry_cli.engine.wait_state import set_run_wait
from foundry_cli.ledger import count_events

BLOCKED_INTAKE_STATUS_CODE = "INTAKE_BLOCKED"


def blocked_intake_request_ref(node_id: str) -> str:
    return f"intake:blocked:{node_id}"


def _blocked_intake_summary(node_id: str) -> str:
    return (
        f"{node_id} is blocked; fix run state (shape or verify context) "
        "and run advance again"
    )


def visit_has_blocked_intake_receipt(snapshot: dict[str, Any], visit_id: str) -> bool:
    return (
        count_events(
            snapshot,
            "receipt.linked",
            visit_id=visit_id,
            schema=INTAKE_RECEIPT_SCHEMA,
        )
        > 0
    )


def intake_validation_findings(
    node_id: str,
    snapshot: dict[str, Any],
    *,
    workspace: Path,
    run_dir: Path,
) -> list[str]:
    if node_id == "execute.intake":
        from foundry_cli.engine.execute_step_executor import _validate_frozen_shape

        return _validate_frozen_shape(snapshot, run_dir)
    if node_id == "verify.intake":
        from foundry_cli.engine.verify_step_executor import (
            _branch_diff_text,
            _validate_verify_intake_context,
        )

        return _validate_verify_intake_context(
            snapshot, workspace, _branch_diff_text(workspace, snapshot)
        )
    return []


def apply_blocked_intake_wait(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """After host intake complete returned blocked without transition."""
    node_id = str(visit.get("node_id", ""))
    visit_id = str(visit.get("id", ""))
    findings = result.get("findings")
    message = (
        "; ".join(str(item) for item in findings)
        if isinstance(findings, list) and findings
        else _blocked_intake_summary(node_id)
    )
    set_status_reason(
        snapshot,
        BLOCKED_INTAKE_STATUS_CODE,
        message=message,
    )
    set_run_wait(
        snapshot,
        kind="operator",
        visit_id=visit_id,
        summary=_blocked_intake_summary(node_id),
        request_ref=blocked_intake_request_ref(node_id),
    )


def host_boundary_wait_blocked_intake(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    *,
    flow: dict[str, Any] | None = None,
    foundry_bundle: Path | None = None,
    workspace: Path | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Hold operator wait until validation passes; avoids duplicate auto-seal on advance."""
    node_id = str(visit.get("node_id", ""))
    if flow is None or foundry_bundle is None:
        return None
    profile = load_node_runtime_profile(node_id, flow, foundry_bundle)
    if not profile.blocked_intake:
        return None
    if str(visit.get("lifecycle")) != LIFECYCLE_OPENED:
        return None
    visit_id = str(visit.get("id", ""))
    if workspace is None or run_dir is None:
        return None
    if not visit_has_blocked_intake_receipt(snapshot, visit_id):
        return None

    findings = intake_validation_findings(node_id, snapshot, workspace=workspace, run_dir=run_dir)
    if not findings:
        clear_status_reason(snapshot)
        return None

    return set_run_wait(
        snapshot,
        kind="operator",
        visit_id=visit_id,
        summary=_blocked_intake_summary(node_id),
        request_ref=blocked_intake_request_ref(node_id),
    )
