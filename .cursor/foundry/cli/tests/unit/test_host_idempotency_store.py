"""Durable host idempotency survives handler re-instantiation."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from foundry_cli.host.handlers import HostHandlers
from foundry_cli.host.idempotency_store import (
    IdempotencyConflictError,
    canonical_request_digest,
    get_cached,
    put_cached,
)
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def test_put_get_cached_round_trip(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    params = {"expected_revision": 1, "idempotency_key": "k1", "run_id": "r1"}
    put_cached(workspace, "k1", {"ok": True, "value": 1}, method="run.advance", params=params)
    assert get_cached(workspace, "k1", method="run.advance", params=params) == {
        "ok": True,
        "value": 1,
    }


def test_expired_idempotency_key_not_returned(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    params = {"idempotency_key": "ttl-key", "expected_revision": 0, "run_id": "r1"}
    put_cached(
        workspace,
        "ttl-key",
        {"ok": True},
        method="run.advance",
        params=params,
        ttl_seconds=0,
    )
    time.sleep(0.02)
    assert get_cached(workspace, "ttl-key", method="run.advance", params=params) is None


def test_conflicting_idempotency_key_raises(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    first_params = {"idempotency_key": "shared", "expected_revision": 1, "run_id": "run-a"}
    second_params = {"idempotency_key": "shared", "expected_revision": 1, "run_id": "run-b"}
    put_cached(workspace, "shared", {"ok": True, "run_id": "run-a"}, method="run.advance", params=first_params)
    with pytest.raises(IdempotencyConflictError):
        get_cached(workspace, "shared", method="run.advance", params=second_params)
    with pytest.raises(IdempotencyConflictError):
        put_cached(
            workspace,
            "shared",
            {"ok": True, "run_id": "run-b"},
            method="run.advance",
            params=second_params,
        )


def test_canonical_digest_ignores_idempotency_key_field() -> None:
    params_a = {"idempotency_key": "a", "expected_revision": 1, "run_id": "r1"}
    params_b = {"idempotency_key": "b", "expected_revision": 1, "run_id": "r1"}
    assert canonical_request_digest("run.advance", params_a) == canonical_request_digest(
        "run.advance",
        params_b,
    )


def test_host_advance_idempotency_survives_restart(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    params = {
        "expected_revision": 1,
        "idempotency_key": "persist-key",
        "run_id": "nope",
    }
    first_handler = HostHandlers(workspace, BUNDLE)
    first = first_handler.dispatch("run.advance", params, "r1")
    second_handler = HostHandlers(workspace, BUNDLE)
    second = second_handler.dispatch("run.advance", params, "r2")
    assert first == second


def test_host_dispatch_returns_conflict_for_key_reuse(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    handler = HostHandlers(workspace, BUNDLE)
    first_params = {
        "expected_revision": 1,
        "idempotency_key": "reuse-key",
        "run_id": "run-a",
    }
    second_params = {
        "expected_revision": 1,
        "idempotency_key": "reuse-key",
        "run_id": "run-b",
    }
    handler.dispatch("run.advance", first_params, "r1")
    conflict = handler.dispatch("run.advance", second_params, "r2")
    assert conflict.get("ok") is False
    assert conflict["error"]["code"] == "IDEMPOTENCY_CONFLICT"
