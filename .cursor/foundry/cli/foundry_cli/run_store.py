"""Load visit-centric run snapshot.json."""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

REVISION_KEY = "revision"
LOCK_FILE_NAME = ".run.lock"


class RunStoreError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def get_revision(snapshot: dict[str, Any]) -> int:
    value = snapshot.get(REVISION_KEY)
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def bump_revision(snapshot: dict[str, Any]) -> int:
    next_revision = get_revision(snapshot) + 1
    snapshot[REVISION_KEY] = next_revision
    return next_revision


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
    """Atomically replace snapshot.json (ledger commits with snapshot)."""
    snapshot_path = run_dir / "snapshot.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    temp_path = snapshot_path.with_suffix(".json.tmp")
    payload = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, snapshot_path)


def _lock_file(handle) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_file(handle) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def run_lock(run_dir: Path) -> Iterator[None]:
    """Exclusive per-run lock for mutation and advance."""
    run_dir.mkdir(parents=True, exist_ok=True)
    lock_path = run_dir / LOCK_FILE_NAME
    with lock_path.open("a+b") as handle:
        _lock_file(handle)
        try:
            yield
        finally:
            _unlock_file(handle)


def commit_snapshot(
    run_dir: Path,
    snapshot: dict[str, Any],
    *,
    expected_revision: int | None = None,
    bump: bool = True,
) -> int:
    """Persist snapshot under lock; optional optimistic revision check."""
    with run_lock(run_dir):
        on_disk = load_snapshot(run_dir)
        disk_revision = get_revision(on_disk)
        if expected_revision is not None and disk_revision != expected_revision:
            raise RunStoreError(
                "STALE_REVISION",
                f"Expected revision {expected_revision}, found {disk_revision}",
            )
        if bump:
            snapshot[REVISION_KEY] = disk_revision + 1
        else:
            snapshot[REVISION_KEY] = disk_revision
        save_snapshot(run_dir, snapshot)
        return get_revision(snapshot)


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
