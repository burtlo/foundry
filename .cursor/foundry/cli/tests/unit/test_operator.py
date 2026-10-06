"""Unit tests for operator run control engine helpers."""

from __future__ import annotations

from foundry_cli.engine.operator import cancel_run, retry_run


def test_retry_not_allowed_on_running() -> None:
    snapshot = {"status": "running", "wait": None, "ledger": []}
    result = retry_run(snapshot)
    assert result.get("ok") is False
    assert result.get("code") == "RETRY_NOT_ALLOWED"


def test_cancel_rejects_empty_reason() -> None:
    snapshot = {"status": "running", "wait": None, "ledger": []}
    result = cancel_run(snapshot, reason="   ")
    assert result.get("ok") is False
    assert result.get("code") == "REASON_REQUIRED"
