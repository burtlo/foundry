"""Shared helpers for Foundry CLI unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.unit.constants import EVENT_VISIT_SEALED


def make_visit(visit_id: str) -> dict[str, str]:
    return {"id": visit_id}


def ledger_visit_sealed(
    node_id: str,
    *,
    outcome: str = "completed",
    seq: int = 1,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "type": EVENT_VISIT_SEALED,
        "node_id": node_id,
        "payload": {"outcome": outcome},
    }


def snapshot_with_visit_sealed(
    node_id: str,
    *,
    outcome: str = "completed",
) -> dict[str, Any]:
    return {"ledger": [ledger_visit_sealed(node_id, outcome=outcome)]}


def prior_visit_sealed_expression(node_id: str) -> str:
    return (
        f"history.last('{EVENT_VISIT_SEALED}', node_id='{node_id}') != null && "
        f"history.last('{EVENT_VISIT_SEALED}', node_id='{node_id}').outcome == 'completed'"
    )


def target_exists(from_file: Path, href: str) -> bool:
    return (from_file.parent / href).resolve().exists()
