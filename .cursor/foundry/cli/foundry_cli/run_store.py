"""Load visit-centric run snapshot.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RunStoreError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_run_dir(
    *,
    run_id: str | None,
    run_dir: Path | None,
    workspace: Path,
) -> Path:
    if run_dir is not None:
        return run_dir.resolve()
    if not run_id:
        raise RunStoreError("RUN_NOT_FOUND", "Provide --run or --run-dir")
    candidate = workspace / ".foundry" / "runs" / run_id
    if candidate.is_dir():
        return candidate.resolve()
    raise RunStoreError("RUN_NOT_FOUND", f"Run directory not found: {candidate}")


def load_snapshot(run_dir: Path) -> dict[str, Any]:
    snapshot_path = run_dir / "snapshot.json"
    if not snapshot_path.is_file():
        raise RunStoreError("RUN_NOT_FOUND", f"Missing snapshot.json in {run_dir}")
    with snapshot_path.open(encoding="utf-8") as handle:
        snapshot = json.load(handle)
    if not isinstance(snapshot, dict):
        raise RunStoreError("RUN_NOT_FOUND", "snapshot.json must be a JSON object")
    return snapshot


def save_snapshot(run_dir: Path, snapshot: dict[str, Any]) -> None:
    snapshot_path = run_dir / "snapshot.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    with snapshot_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")


def select_visit(snapshot: dict[str, Any], visit_id: str | None) -> dict[str, Any]:
    visits = snapshot.get("visits")
    if visit_id and isinstance(visits, list):
        for visit in visits:
            if isinstance(visit, dict) and visit.get("id") == visit_id:
                return visit
        raise RunStoreError("VISIT_NOT_FOUND", f"Visit {visit_id!r} not found in snapshot")

    active = snapshot.get("active_visit")
    if isinstance(active, dict):
        if visit_id and active.get("id") != visit_id:
            raise RunStoreError("VISIT_NOT_FOUND", f"Visit {visit_id!r} is not the active visit")
        return active

    if visit_id:
        raise RunStoreError("VISIT_NOT_FOUND", f"No visit {visit_id!r} in snapshot")
    raise RunStoreError("VISIT_NOT_FOUND", "Snapshot has no active_visit")
