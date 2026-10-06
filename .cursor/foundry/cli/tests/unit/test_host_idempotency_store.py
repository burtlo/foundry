"""Durable host idempotency survives handler re-instantiation."""

from __future__ import annotations

import time
from pathlib import Path

from foundry_cli.host.handlers import HostHandlers
from foundry_cli.host.idempotency_store import get_cached, put_cached
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def test_put_get_cached_round_trip(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    put_cached(workspace, "k1", {"ok": True, "value": 1})
    assert get_cached(workspace, "k1") == {"ok": True, "value": 1}


def test_expired_idempotency_key_not_returned(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    put_cached(workspace, "ttl-key", {"ok": True}, ttl_seconds=0)
    time.sleep(0.02)
    assert get_cached(workspace, "ttl-key") is None


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
