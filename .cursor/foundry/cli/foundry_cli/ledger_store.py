"""Append-only per-run ledger file (ledger.jsonl)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

LEDGER_FILE_NAME = "ledger.jsonl"
STORAGE_VERSION_KEY = "storage_version"
STORAGE_VERSION_V2 = 2


class LedgerStoreError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def ledger_path(run_dir: Path) -> Path:
    return run_dir / LEDGER_FILE_NAME


def read_ledger_file(run_dir: Path) -> list[dict[str, Any]]:
    path = ledger_path(run_dir)
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise LedgerStoreError(
                    "LEDGER_CORRUPT",
                    f"Invalid JSON at {path}:{line_no}: {exc}",
                ) from exc
            if not isinstance(parsed, dict):
                raise LedgerStoreError(
                    "LEDGER_CORRUPT",
                    f"Ledger line {line_no} must be a JSON object",
                )
            events.append(parsed)
    return events


def max_seq(events: list[dict[str, Any]]) -> int:
    if not events:
        return 0
    return max(int(event.get("seq", 0)) for event in events if isinstance(event, dict))


def append_events(run_dir: Path, events: list[dict[str, Any]]) -> None:
    """Append one JSON event per line; fsync after each append batch."""
    if not events:
        return
    run_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_path(run_dir)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_ledger_file(run_dir: Path, events: list[dict[str, Any]]) -> None:
    """Replace ledger.jsonl atomically (migration / full rewrite)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_path(run_dir)
    temp = path.with_suffix(".jsonl.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def events_after_seq(events: list[dict[str, Any]], after_seq: int) -> list[dict[str, Any]]:
    pending = [
        event
        for event in events
        if isinstance(event, dict) and int(event.get("seq", 0)) > after_seq
    ]
    pending.sort(key=lambda e: int(e.get("seq", 0)))
    return pending


def migrate_run_storage(run_dir: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Idempotent migration from inline-only ledger to ledger.jsonl + storage_version 2."""
    version = snapshot.get(STORAGE_VERSION_KEY)
    path = ledger_path(run_dir)
    inline = snapshot.get("ledger")
    inline_events: list[dict[str, Any]] = []
    if isinstance(inline, list):
        inline_events = [e for e in inline if isinstance(e, dict)]

    if path.is_file():
        file_events = read_ledger_file(run_dir)
        file_max = max_seq(file_events)
        if version != STORAGE_VERSION_V2:
            snapshot[STORAGE_VERSION_KEY] = STORAGE_VERSION_V2
        if inline_events and max_seq(inline_events) > file_max:
            to_append = events_after_seq(inline_events, file_max)
            append_events(run_dir, to_append)
            file_events = read_ledger_file(run_dir)
        if not inline_events or max_seq(inline_events) < max_seq(file_events):
            snapshot["ledger"] = file_events
        return snapshot

    if inline_events:
        write_ledger_file(run_dir, sorted(inline_events, key=lambda e: int(e.get("seq", 0))))
    snapshot[STORAGE_VERSION_KEY] = STORAGE_VERSION_V2
    return snapshot


def sync_snapshot_ledger_from_file(run_dir: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Ensure snapshot inline ledger matches ledger.jsonl when the file exists."""
    path = ledger_path(run_dir)
    if not path.is_file():
        return snapshot
    file_events = read_ledger_file(run_dir)
    snapshot["ledger"] = file_events
    snapshot[STORAGE_VERSION_KEY] = STORAGE_VERSION_V2
    return snapshot


def repair_snapshot_from_ledger(run_dir: Path, partial: dict[str, Any] | None) -> dict[str, Any]:
    """Rebuild ledger (and preserve revision when possible) from committed ledger.jsonl."""
    file_events = read_ledger_file(run_dir)
    if not file_events:
        raise LedgerStoreError("LEDGER_CORRUPT", "ledger.jsonl is empty; cannot repair snapshot")
    base: dict[str, Any] = dict(partial) if isinstance(partial, dict) else {}
    base["ledger"] = file_events
    base[STORAGE_VERSION_KEY] = STORAGE_VERSION_V2
    revision = base.get("revision")
    if revision is None:
        base["revision"] = 0
    return base
