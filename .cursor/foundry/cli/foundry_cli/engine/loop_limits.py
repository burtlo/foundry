"""Repair and re-verify loop limit checks (flow catalog parity with resolvers and hooks)."""

from __future__ import annotations

from typing import Any

from foundry_cli.ledger import count_events


def _config_limit(snapshot: dict[str, Any], name: str, default: int) -> int:
    config = snapshot.get("config")
    if isinstance(config, dict):
        limits = config.get("limits")
        if isinstance(limits, dict):
            value = limits.get(name)
            if isinstance(value, (int, float)):
                return int(value)
    return default

LIMIT_FLOW_CHECK_IDS: frozenset[str] = frozenset(
    {
        "repair-within-limit",
        "reverify-within-limit",
    }
)


def repair_loop_summary_for_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Ledger repair-loop count vs config.limits.repair."""
    repair_count = count_events(snapshot, "connection.taken", loop="repair")
    limit = _config_limit(snapshot, "repair", 2)
    return {
        "repair_count": repair_count,
        "limit": limit,
        "within_limit": repair_count <= limit,
    }


def reverify_loop_summary_for_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Prior verify.intake seals vs config.limits.reverify for commit gate context."""
    reverify_count = count_events(snapshot, "visit.sealed", node_id="verify.intake")
    limit = _config_limit(snapshot, "reverify", 2)
    return {
        "reverify_count": reverify_count,
        "limit": limit,
        "within_limit": reverify_count <= limit,
    }


def evaluate_limit_flow_check(snapshot: dict[str, Any], check_id: str) -> bool | None:
    """Return pass/fail for catalog limit checks; None when check_id is not a limit check."""
    if check_id == "repair-within-limit":
        return repair_loop_summary_for_snapshot(snapshot)["within_limit"]
    if check_id == "reverify-within-limit":
        return reverify_loop_summary_for_snapshot(snapshot)["within_limit"]
    return None
