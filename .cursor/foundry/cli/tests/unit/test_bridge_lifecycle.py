"""Unit tests for judgment bridge lifecycle (mocked spawn and health)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from foundry_cli.bridge.discovery import read_state, write_state
from foundry_cli.bridge.lifecycle import reconcile_bridge, stop_bridge
from foundry_cli.bridge.paths import DEFAULT_BRIDGE_HOST, DEFAULT_BRIDGE_PORT
from foundry_cli.judgment_bridge.server import DEFAULT_AGENT_PATH
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def _healthy_state(workspace: Path, pid: int = 4242) -> None:
    write_state(
        workspace,
        pid=pid,
        listen_host=DEFAULT_BRIDGE_HOST,
        listen_port=DEFAULT_BRIDGE_PORT,
        agent_path=DEFAULT_AGENT_PATH,
        bound_workspace=workspace,
    )


def test_reconcile_restarts_when_bound_workspace_mismatch(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    other_workspace = tmp_path / "other-app"
    other_workspace.mkdir()
    write_state(
        workspace,
        pid=4242,
        listen_host=DEFAULT_BRIDGE_HOST,
        listen_port=DEFAULT_BRIDGE_PORT,
        agent_path=DEFAULT_AGENT_PATH,
        bound_workspace=other_workspace,
    )
    mock_proc = MagicMock()
    mock_proc.pid = 6666

    with patch("foundry_cli.bridge.lifecycle.pid_alive", return_value=True):
        with patch(
            "foundry_cli.bridge.lifecycle._probe_health",
            return_value={"ok": True, "detail": "healthy"},
        ):
            with patch(
                "foundry_cli.judgment_bridge.keys.resolve_cursor_api_key",
            ):
                with patch(
                    "foundry_cli.bridge.lifecycle._spawn_detached_bridge",
                    return_value=mock_proc,
                ) as spawn:
                    with patch("foundry_cli.bridge.lifecycle._terminate_pid") as terminate:
                        with patch("time.sleep"):
                            result = reconcile_bridge(workspace, BUNDLE)

    terminate.assert_called_once_with(4242)
    spawn.assert_called_once()
    assert result.get("ok") is True
    assert result.get("started") is True
    assert result.get("pid") == 6666
    state = read_state(workspace)
    assert state is not None
    assert state.get("workspace") == str(workspace.resolve())


def test_reconcile_returns_already_running_when_healthy_and_config_matches(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    _healthy_state(workspace)
    with patch("foundry_cli.bridge.lifecycle.pid_alive", return_value=True):
        with patch(
            "foundry_cli.bridge.lifecycle._probe_health",
            return_value={"ok": True, "detail": "healthy"},
        ):
            result = reconcile_bridge(workspace, BUNDLE)

    assert result.get("ok") is True
    assert result.get("already_running") is True
    assert result.get("pid") == 4242
    assert "bridge_url" in result


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("listen_host", "0.0.0.0"),
        ("listen_port", 9999),
        ("agent_path", "/v2/other"),
    ],
)
def test_reconcile_restarts_when_listen_config_mismatch(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    _healthy_state(workspace)
    kwargs = {
        "listen_host": DEFAULT_BRIDGE_HOST,
        "listen_port": DEFAULT_BRIDGE_PORT,
        "agent_path": DEFAULT_AGENT_PATH,
    }
    kwargs[field] = value  # type: ignore[literal-required]

    mock_proc = MagicMock()
    mock_proc.pid = 7777

    with patch("foundry_cli.bridge.lifecycle.pid_alive", return_value=True):
        with patch(
            "foundry_cli.bridge.lifecycle._probe_health",
            return_value={"ok": True, "detail": "healthy"},
        ):
            with patch(
                "foundry_cli.judgment_bridge.keys.resolve_cursor_api_key",
            ):
                with patch(
                    "foundry_cli.bridge.lifecycle._spawn_detached_bridge",
                    return_value=mock_proc,
                ) as spawn:
                    with patch("time.sleep"):
                        result = reconcile_bridge(workspace, BUNDLE, **kwargs)

    spawn.assert_called_once()
    assert result.get("ok") is True
    assert result.get("started") is True
    assert result.get("pid") == 7777


def test_reconcile_configuration_error_when_api_key_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    with patch("foundry_cli.bridge.lifecycle.pid_alive", return_value=False):
        with patch(
            "foundry_cli.judgment_bridge.keys.resolve_cursor_api_key",
            side_effect=RuntimeError("missing key"),
        ):
            result = reconcile_bridge(workspace, BUNDLE)

    assert result.get("ok") is False
    err = result.get("error") or {}
    assert err.get("code") == "CONFIGURATION_ERROR"
    assert "missing key" in str(err.get("message") or "")


def test_reconcile_bridge_start_failed_when_health_never_ok(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    mock_proc = MagicMock()
    mock_proc.pid = 8888

    with patch("foundry_cli.bridge.lifecycle.pid_alive", return_value=True):
        with patch(
            "foundry_cli.bridge.lifecycle._probe_health",
            return_value={"ok": False, "detail": "down"},
        ):
            with patch(
                "foundry_cli.judgment_bridge.keys.resolve_cursor_api_key",
            ):
                with patch(
                    "foundry_cli.bridge.lifecycle._spawn_detached_bridge",
                    return_value=mock_proc,
                ):
                    with patch("time.sleep"):
                        result = reconcile_bridge(workspace, BUNDLE)

    assert result.get("ok") is False
    assert (result.get("error") or {}).get("code") == "BRIDGE_START_FAILED"
    assert read_state(workspace) is None


def test_reconcile_starts_bridge_when_not_running(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    mock_proc = MagicMock()
    mock_proc.pid = 5555

    with patch("foundry_cli.bridge.lifecycle.pid_alive", return_value=True):
        with patch(
            "foundry_cli.bridge.lifecycle._probe_health",
            return_value={"ok": True, "detail": "healthy"},
        ):
            with patch(
                "foundry_cli.judgment_bridge.keys.resolve_cursor_api_key",
            ):
                with patch(
                    "foundry_cli.bridge.lifecycle._spawn_detached_bridge",
                    return_value=mock_proc,
                ) as spawn:
                    with patch("time.sleep"):
                        result = reconcile_bridge(workspace, BUNDLE)

    spawn.assert_called_once()
    argv = spawn.call_args[0][0]
    assert "-m" in argv
    assert "foundry_cli.judgment_bridge" in argv
    assert result.get("ok") is True
    assert result.get("started") is True
    state = read_state(workspace)
    assert state is not None
    assert state["pid"] == 5555


def test_stop_bridge_clears_state(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    _healthy_state(workspace, pid=3333)
    with patch("foundry_cli.bridge.lifecycle.pid_alive", return_value=True):
        with patch("foundry_cli.bridge.lifecycle._terminate_pid") as terminate:
            result = stop_bridge(workspace)

    terminate.assert_called_once_with(3333)
    assert result.get("ok") is True
    assert result.get("was_running") is True
    assert read_state(workspace) is None
