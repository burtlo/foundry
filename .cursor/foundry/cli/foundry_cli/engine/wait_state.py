"""Run wait boundary helpers."""

from __future__ import annotations

import uuid
from typing import Any

from foundry_cli.util import now_iso


def _new_wait_id() -> str:
    return f"w_{uuid.uuid4().hex[:12]}"


def set_run_wait(
    snapshot: dict[str, Any],
    *,
    kind: str,
    visit_id: str,
    summary: str,
    request_ref: str | None = None,
) -> dict[str, Any]:
    existing = snapshot.get("wait")
    if isinstance(existing, dict):
        if (
            existing.get("kind") == kind
            and existing.get("visit_id") == visit_id
            and existing.get("request_ref") == request_ref
        ):
            return existing
    wait = {
        "id": _new_wait_id(),
        "visit_id": visit_id,
        "kind": kind,
        "created_at": now_iso(),
        "request_ref": request_ref,
        "summary": summary,
    }
    snapshot["wait"] = wait
    return wait


def clear_run_wait(snapshot: dict[str, Any]) -> None:
    snapshot["wait"] = None
