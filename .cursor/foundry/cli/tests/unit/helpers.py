"""Shared helpers for Foundry CLI unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.unit.constants import EVENT_VISIT_SEALED


def make_visit(visit_id: str) -> dict[str, str]:
    return {"id": visit_id}


def ledger_check_recorded(
    gate_visit_id: str,
    *,
    gate_node_id: str,
    check_id: str,
    result: str = "pass",
    hook: str = "on_examine",
    seq: int = 1,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "type": "check.recorded",
        "visit_id": gate_visit_id,
        "node_id": gate_node_id,
        "payload": {"hook": hook, "check_id": check_id, "result": result},
    }


def seed_gate_examine_passes(
    snapshot: dict[str, Any],
    gate_visit: dict[str, Any],
    check_ids: tuple[str, ...] | list[str],
    *,
    start_seq: int | None = None,
) -> None:
    """Append passing on_examine check.recorded rows for engine gate resolver tests."""
    ledger = list(snapshot.get("ledger") or [])
    seq = start_seq if start_seq is not None else (max(int(e.get("seq", 0)) for e in ledger) + 1 if ledger else 1)
    gate_visit_id = str(gate_visit["id"])
    gate_node_id = str(gate_visit["node_id"])
    for check_id in check_ids:
        ledger.append(
            ledger_check_recorded(
                gate_visit_id,
                gate_node_id=gate_node_id,
                check_id=check_id,
                seq=seq,
            )
        )
        seq += 1
    snapshot["ledger"] = ledger


def ledger_visit_sealed(
    node_id: str,
    *,
    visit_id: str | None = None,
    outcome: str = "completed",
    seq: int = 1,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "seq": seq,
        "type": EVENT_VISIT_SEALED,
        "node_id": node_id,
        "payload": {"outcome": outcome},
    }
    if visit_id is not None:
        entry["visit_id"] = visit_id
    return entry


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
