"""Transition-time policy enforced by the engine (not steward prose)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from foundry_cli.constants import EVENT_RECEIPT_LINKED
from foundry_cli.node_operations import load_operations
from foundry_cli.registry import get_node

INTAKE_RECEIPT_SCHEMA = "registry:schemas/intake-receipt.schema.json"
INTAKE_BLOCKED_CODE = "INTAKE_BLOCKED"


def _visit_receipt_linked(snapshot: dict[str, Any], visit_id: str, schema_ref: str) -> bool:
    ledger = snapshot.get("ledger")
    if not isinstance(ledger, list):
        return False
    for event in ledger:
        if not isinstance(event, dict):
            continue
        if event.get("type") != EVENT_RECEIPT_LINKED:
            continue
        if str(event.get("visit_id")) != visit_id:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if str(payload.get("schema")) == schema_ref:
            return True
    return False


def _read_intake_receipt_status(run_dir: Path) -> str | None:
    path = run_dir / "receipts" / "intake.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    status = data.get("status")
    return str(status) if status is not None else None


def _transition_rules_for_visit(
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    foundry_bundle: Path,
) -> list[dict[str, Any]]:
    node_id = str(visit.get("node_id", ""))
    if not node_id:
        return []
    try:
        node = get_node(flow, node_id)
    except KeyError:
        return []
    operations_ref = node.get("operations")
    if not isinstance(operations_ref, str) or not operations_ref.strip():
        return []
    try:
        operations = load_operations(operations_ref.strip(), foundry_bundle)
    except Exception:
        return []
    completion = operations.get("policy")
    if not isinstance(completion, dict):
        return []
    completion = completion.get("completion")
    if not isinstance(completion, dict):
        return []
    transition = completion.get("transition")
    if not isinstance(transition, list):
        return []
    rules: list[dict[str, Any]] = []
    for item in transition:
        if isinstance(item, dict):
            rules.append(item)
    return rules


def _when_matches_blocked_intake(when_expr: Any, intake_status: str | None) -> bool:
    if intake_status != "blocked":
        return False
    if when_expr is None:
        return True
    if not isinstance(when_expr, str):
        return False
    normalized = " ".join(when_expr.strip().split()).lower()
    return normalized in {
        "intake_receipt.status == blocked",
        "intake_receipt.status == 'blocked'",
        'intake_receipt.status == "blocked"',
    }


def _deny_from_rule(
    rule: dict[str, Any],
    *,
    intake_status: str | None,
    node_id: str,
) -> dict[str, Any] | None:
    rule_id = str(rule.get("rule") or "")
    if rule_id == "intake_receipt_not_blocked" and intake_status == "blocked":
        return {
            "ok": False,
            "code": str(rule.get("code") or INTAKE_BLOCKED_CODE),
            "message": (
                f"{node_id} intake receipt status is blocked; resolve blockers and "
                "re-run intake before transition."
            ),
        }

    denies = rule.get("denies")
    if (
        isinstance(denies, list)
        and any(str(item) == "transition" for item in denies)
        and _when_matches_blocked_intake(rule.get("when"), intake_status)
    ):
        return {
            "ok": False,
            "code": str(rule.get("code") or INTAKE_BLOCKED_CODE),
            "message": (
                f"{node_id} transition denied while intake status is blocked."
            ),
        }
    return None


def enforce_transition_policy(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    *,
    flow: dict[str, Any],
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any]:
    """Return ok=False when engine policy blocks visit transition."""
    visit_id = str(visit.get("id", ""))
    node_id = str(visit.get("node_id", ""))
    intake_status: str | None = None
    if _visit_receipt_linked(snapshot, visit_id, INTAKE_RECEIPT_SCHEMA):
        intake_status = _read_intake_receipt_status(run_dir)
    for rule in _transition_rules_for_visit(
        visit,
        flow,
        foundry_bundle=foundry_bundle,
    ):
        denied = _deny_from_rule(
            rule,
            intake_status=intake_status,
            node_id=node_id,
        )
        if denied is not None:
            return denied

    return {"ok": True}
