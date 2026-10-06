"""Load visit-centric run snapshot.json."""

from __future__ import annotations

import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from foundry_cli.ledger_store import (
    append_events,
    events_after_seq,
    ledger_path,
    max_seq,
    migrate_run_storage,
    read_ledger_file,
    repair_snapshot_from_ledger,
    sync_snapshot_ledger_from_file,
)

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


def _read_snapshot_file(snapshot_path: Path) -> dict[str, Any]:
    with snapshot_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _try_partial_snapshot(snapshot_path: Path) -> dict[str, Any] | None:
    try:
        text = snapshot_path.read_text(encoding="utf-8")
    except OSError:
        return None
    partial: dict[str, Any] = {}
    run_match = re.search(r'"run_id"\s*:\s*"([^"]+)"', text)
    if run_match:
        partial["run_id"] = run_match.group(1)
    rev_match = re.search(r'"revision"\s*:\s*(\d+)', text)
    if rev_match:
        partial[REVISION_KEY] = int(rev_match.group(1))
    return partial or None


def load_snapshot(run_dir: Path) -> dict[str, Any]:
    snapshot_path = run_dir / "snapshot.json"
    if not snapshot_path.is_file():
        if ledger_path(run_dir).is_file():
            snapshot = repair_snapshot_from_ledger(run_dir, None)
            save_snapshot(run_dir, snapshot)
            return snapshot
        raise RunStoreError("RUN_NOT_FOUND", f"Missing snapshot.json in {run_dir}")
    snapshot: dict[str, Any] | None = None
    try:
        loaded = _read_snapshot_file(snapshot_path)
        if not isinstance(loaded, dict):
            raise RunStoreError("RUN_NOT_FOUND", "snapshot.json must be a JSON object")
        snapshot = loaded
    except (json.JSONDecodeError, OSError):
        snapshot = None
    if snapshot is None:
        if not ledger_path(run_dir).is_file():
            raise RunStoreError("RUN_NOT_FOUND", f"Corrupt snapshot.json in {run_dir}")
        snapshot = repair_snapshot_from_ledger(run_dir, _try_partial_snapshot(snapshot_path))
        save_snapshot(run_dir, snapshot)
        return snapshot
    snapshot = migrate_run_storage(run_dir, snapshot)
    if ledger_path(run_dir).is_file():
        file_events = read_ledger_file(run_dir)
        inline = snapshot.get("ledger")
        inline_max = max_seq(inline) if isinstance(inline, list) else 0
        file_max = max_seq(file_events)
        if file_max > inline_max:
            snapshot = sync_snapshot_ledger_from_file(run_dir, snapshot)
            save_snapshot(run_dir, snapshot)
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


def _pending_ledger_appends(run_dir: Path, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    ledger = snapshot.get("ledger")
    if not isinstance(ledger, list):
        return []
    incoming = [e for e in ledger if isinstance(e, dict)]
    if ledger_path(run_dir).is_file():
        committed = read_ledger_file(run_dir)
        return events_after_seq(incoming, max_seq(committed))
    on_disk_path = run_dir / "snapshot.json"
    if on_disk_path.is_file():
        try:
            on_disk = _read_snapshot_file(on_disk_path)
            if isinstance(on_disk, dict):
                prior = on_disk.get("ledger")
                if isinstance(prior, list):
                    return events_after_seq(incoming, max_seq(prior))
        except (json.JSONDecodeError, OSError):
            pass
    return incoming


def commit_snapshot(
    run_dir: Path,
    snapshot: dict[str, Any],
    *,
    expected_revision: int | None = None,
    bump: bool = True,
) -> int:
    """Persist new ledger events then snapshot under lock; optional optimistic revision check."""
    with run_lock(run_dir):
        snapshot_path = run_dir / "snapshot.json"
        if snapshot_path.is_file():
            on_disk = load_snapshot(run_dir)
            disk_revision = get_revision(on_disk)
        else:
            disk_revision = 0
        if expected_revision is not None and disk_revision != expected_revision:
            raise RunStoreError(
                "STALE_REVISION",
                f"Expected revision {expected_revision}, found {disk_revision}",
            )
        if bump:
            snapshot[REVISION_KEY] = disk_revision + 1
        else:
            snapshot[REVISION_KEY] = disk_revision
        pending = _pending_ledger_appends(run_dir, snapshot)
        if pending:
            append_events(run_dir, pending)
        snapshot = migrate_run_storage(run_dir, snapshot)
        snapshot = sync_snapshot_ledger_from_file(run_dir, snapshot)
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
