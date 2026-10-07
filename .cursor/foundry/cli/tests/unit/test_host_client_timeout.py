"""Host RPC client socket timeout policy."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from foundry_cli.engine.agent.tasks import max_judgment_task_timeout_seconds
from foundry_cli.host.client import call_host
from foundry_cli.host.timeout_policy import (
    DEFAULT_HOST_CLIENT_TIMEOUT_SECONDS,
    client_timeout_for_method,
    client_timeout_for_run_advance,
)
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def test_health_uses_default_timeout() -> None:
    assert client_timeout_for_method("health", {}) == DEFAULT_HOST_CLIENT_TIMEOUT_SECONDS


def test_run_events_timeout_includes_block_ms() -> None:
    timeout = client_timeout_for_method("run.events", {"block_ms": 5000})
    assert timeout > DEFAULT_HOST_CLIENT_TIMEOUT_SECONDS + 4.0


def test_run_advance_default_budget_exceeds_three_minutes() -> None:
    timeout = client_timeout_for_run_advance({"step_budget": 8}, bundle=BUNDLE)
    assert timeout >= 180.0


def test_run_advance_scales_with_step_budget() -> None:
    small = client_timeout_for_run_advance({"step_budget": 1}, bundle=BUNDLE)
    large = client_timeout_for_run_advance({"step_budget": 8}, bundle=BUNDLE)
    assert large > small


def test_run_advance_respects_client_timeout_hint() -> None:
    timeout = client_timeout_for_run_advance(
        {"step_budget": 1, "client_timeout_hint_seconds": 600},
        bundle=BUNDLE,
    )
    assert timeout >= 600.0


def test_run_advance_uses_registry_judgment_task_limit() -> None:
    judgment_max = float(max_judgment_task_timeout_seconds(BUNDLE))
    per_round = judgment_max + 15.0
    expected = 10.0 + per_round
    assert client_timeout_for_run_advance({"step_budget": 1}, bundle=BUNDLE) == expected


@patch("foundry_cli.host.client.host_is_running", return_value=True)
@patch("foundry_cli.host.client.read_state")
@patch("foundry_cli.host.client._connect")
def test_call_host_advance_sets_extended_socket_timeout(
    mock_connect: MagicMock,
    mock_read_state: MagicMock,
    _mock_running: MagicMock,
    tmp_path,
) -> None:
    mock_read_state.return_value = {
        "transport": "unix",
        "address": str(tmp_path / "sock"),
        "pid": 1,
    }
    sock = MagicMock()
    mock_connect.return_value = sock
    response_line = (
        b'{"protocol_version":1,"id":"r1","ok":true,'
        b'"result":{"ok":true,"revision":1}}\n'
    )
    sock.recv.side_effect = [response_line]

    call_host(
        tmp_path,
        "run.advance",
        {
            "run_id": "test-run",
            "expected_revision": 0,
            "step_budget": 8,
            "idempotency_key": "k",
        },
    )

    sock.settimeout.assert_called_once()
    applied = float(sock.settimeout.call_args[0][0])
    assert applied >= 180.0


@patch("foundry_cli.host.client.host_is_running", return_value=True)
@patch("foundry_cli.host.client.read_state")
@patch("foundry_cli.host.client._connect")
def test_call_host_explicit_timeout_override(
    mock_connect: MagicMock,
    mock_read_state: MagicMock,
    _mock_running: MagicMock,
    tmp_path,
) -> None:
    mock_read_state.return_value = {
        "transport": "unix",
        "address": str(tmp_path / "sock"),
        "pid": 1,
    }
    sock = MagicMock()
    mock_connect.return_value = sock
    sock.recv.return_value = (
        b'{"protocol_version":1,"id":"r1","ok":true,'
        b'"result":{"ok":true}}\n'
    )

    call_host(tmp_path, "health", {}, timeout=5.0)

    sock.settimeout.assert_called_once_with(5.0)
