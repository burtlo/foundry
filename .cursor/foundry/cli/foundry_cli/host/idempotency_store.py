"""Durable host mutation idempotency keys (survives host restart)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from foundry_cli.host.paths import host_dir

IDEMPOTENCY_FILE_NAME = "idempotency.json"
DEFAULT_TTL_SECONDS = 24 * 60 * 60
MAX_ENTRIES = 1000


class IdempotencyConflictError(Exception):
    def __init__(self, message: str = "Idempotency key reused with a different mutation") -> None:
        super().__init__(message)
        self.code = "IDEMPOTENCY_CONFLICT"
        self.message = message


def idempotency_path(workspace: Path) -> Path:
    return host_dir(workspace) / IDEMPOTENCY_FILE_NAME


def _now_epoch() -> float:
    return time.time()


def canonical_request_digest(method: str, params: dict[str, Any]) -> str:
    filtered = {str(k): params[k] for k in sorted(params) if k != "idempotency_key"}
    payload = {"method": method, "params": filtered}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def load_store(workspace: Path) -> dict[str, dict[str, Any]]:
    path = idempotency_path(workspace)
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    entries = data.get("entries")
    if not isinstance(entries, dict):
        return {}
    return {str(k): v for k, v in entries.items() if isinstance(v, dict)}


def _prune(entries: dict[str, dict[str, Any]], *, ttl_seconds: int) -> dict[str, dict[str, Any]]:
    now = _now_epoch()
    kept: dict[str, dict[str, Any]] = {}
    for key, record in entries.items():
        expires = float(record.get("expires_at", 0))
        if expires > now:
            kept[key] = record
    if len(kept) > MAX_ENTRIES:
        ordered = sorted(kept.items(), key=lambda item: float(item[1].get("expires_at", 0)))
        kept = dict(ordered[-MAX_ENTRIES:])
    return kept


def save_store(workspace: Path, entries: dict[str, dict[str, Any]], *, ttl_seconds: int) -> None:
    pruned = _prune(entries, ttl_seconds=ttl_seconds)
    directory = host_dir(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    path = idempotency_path(workspace)
    temp = path.with_suffix(".json.tmp")
    payload = json.dumps({"entries": pruned}, indent=2, sort_keys=True) + "\n"
    with temp.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def get_cached(
    workspace: Path,
    key: str,
    *,
    method: str | None = None,
    params: dict[str, Any] | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any] | None:
    entries = load_store(workspace)
    record = entries.get(key)
    if record is None:
        return None
    if float(record.get("expires_at", 0)) <= _now_epoch():
        return None
    if method is not None and params is not None:
        digest = canonical_request_digest(method, params)
        stored_method = record.get("method")
        stored_digest = record.get("request_digest")
        if stored_method != method or stored_digest != digest:
            raise IdempotencyConflictError(
                f"Idempotency key {key!r} was used for a different mutation",
            )
    result = record.get("result")
    return result if isinstance(result, dict) else None


def put_cached(
    workspace: Path,
    key: str,
    result: dict[str, Any],
    *,
    method: str,
    params: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    digest = canonical_request_digest(method, params)
    entries = load_store(workspace)
    existing = entries.get(key)
    if existing is not None and float(existing.get("expires_at", 0)) > _now_epoch():
        if existing.get("method") != method or existing.get("request_digest") != digest:
            raise IdempotencyConflictError(
                f"Idempotency key {key!r} was used for a different mutation",
            )
    entries[key] = {
        "method": method,
        "request_digest": digest,
        "result": result,
        "expires_at": _now_epoch() + ttl_seconds,
    }
    save_store(workspace, entries, ttl_seconds=ttl_seconds)
