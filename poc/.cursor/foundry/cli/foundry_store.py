"""Crash-resistant local persistence primitives for Foundry run artifacts."""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class StoreError(Exception):
    def __init__(self, error_code: str, message: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.extra = extra or {}


def _lock_path(run_dir: Path) -> Path:
    return run_dir / ".foundry-write.lock"


@contextmanager
def run_lease(run_dir: Path, *, timeout_seconds: float = 10.0, stale_seconds: float = 120.0) -> Iterator[str]:
    """Acquire an exclusive, cross-process lock using atomic file creation."""
    run_dir.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(run_dir)
    owner = str(uuid.uuid4())
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"owner": owner, "pid": os.getpid(), "created_unix": time.time()}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            break
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > stale_seconds:
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise StoreError(
                    "RUN_LEASE_TIMEOUT",
                    f"Timed out acquiring Foundry run lease: {lock_path}",
                    extra={"lock_path": str(lock_path)},
                )
            time.sleep(0.05)
    try:
        yield owner
    finally:
        try:
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            payload = {}
        if payload.get("owner") == owner:
            lock_path.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_revision(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoreError("INVALID_STATE", f"Run state is not valid JSON: {path}") from exc
    return int(payload.get("state_revision") or 0)


def write_state_cas(path: Path, state: dict[str, Any], *, expected_revision: int) -> str:
    """Atomically replace state when its on-disk revision still matches."""
    with run_lease(path.parent):
        actual_revision = read_revision(path)
        if actual_revision != expected_revision:
            raise StoreError(
                "STALE_STATE_REVISION",
                "Run state changed after it was loaded; reload before retrying.",
                extra={"expected_revision": expected_revision, "actual_revision": actual_revision},
            )
        transaction_id = str(uuid.uuid4())
        journal_path = path.parent / "transactions.jsonl"
        _append_jsonl_unlocked(
            journal_path,
            {
                "transaction_id": transaction_id,
                "status": "prepared",
                "expected_revision": actual_revision,
                "next_revision": actual_revision + 1,
            },
        )
        state["state_revision"] = actual_revision + 1
        state["last_transaction_id"] = transaction_id
        atomic_write_text(path, json.dumps(state, indent=2) + "\n")
        _append_jsonl_unlocked(
            journal_path,
            {
                "transaction_id": transaction_id,
                "status": "committed",
                "state_revision": actual_revision + 1,
            },
        )
        return transaction_id


def _append_jsonl_unlocked(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """Append one durable JSONL record while holding the run lease."""
    with run_lease(path.parent):
        _append_jsonl_unlocked(path, payload)


def recover_run(run_dir: Path) -> dict[str, Any]:
    """Remove abandoned temp files and report state/event transaction alignment."""
    removed: list[str] = []
    for temporary in run_dir.glob(".*.tmp"):
        removed.append(temporary.name)
        temporary.unlink(missing_ok=True)
    state_path = run_dir / "state.json"
    events_path = run_dir / "events.jsonl"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    last_transaction_id = state.get("last_transaction_id")
    event_transaction_ids: set[str] = set()
    if events_path.is_file():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            transaction_id = event.get("transaction_id")
            if isinstance(transaction_id, str):
                event_transaction_ids.add(transaction_id)
    committed_transaction_ids: set[str] = set()
    journal_path = run_dir / "transactions.jsonl"
    if journal_path.is_file():
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("status") == "committed" and isinstance(item.get("transaction_id"), str):
                committed_transaction_ids.add(item["transaction_id"])
    return {
        "removed_temporary_files": removed,
        "state_revision": int(state.get("state_revision") or 0),
        "last_transaction_id": last_transaction_id,
        "last_transaction_has_event": (
            last_transaction_id in event_transaction_ids if last_transaction_id else None
        ),
        "last_transaction_committed": (
            last_transaction_id in committed_transaction_ids if last_transaction_id else None
        ),
    }
