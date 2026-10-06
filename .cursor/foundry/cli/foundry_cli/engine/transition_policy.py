"""Transition-time policy enforced by the engine (not steward prose)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from foundry_cli.constants import EVENT_RECEIPT_LINKED

INTAKE_RECEIPT_SCHEMA = "registry:schemas/intake-receipt.schema.json"


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


def enforce_transition_policy(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    """Return ok=False when engine policy blocks visit transition."""
    node_id = str(visit.get("node_id", ""))
    visit_id = str(visit.get("id", ""))

    if node_id == "shape.intake":
        if _visit_receipt_linked(snapshot, visit_id, INTAKE_RECEIPT_SCHEMA):
            status = _read_intake_receipt_status(run_dir)
            if status == "blocked":
                return {
                    "ok": False,
                    "code": "INTAKE_BLOCKED",
                    "message": (
                        "Intake receipt status is blocked; resolve blockers and re-run intake "
                        "before transition."
                    ),
                }

    return {"ok": True}
