"""Unit tests for judgment bridge discovery helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_cli.bridge.discovery import (
    bridge_health_base_url,
    bridge_http_url,
    bridge_is_running,
    clear_state,
    read_state,
    write_state,
)
from foundry_cli.bridge.paths import state_path
from foundry_cli.judgment_bridge.server import DEFAULT_AGENT_PATH


def test_write_state_and_read_state_round_trip(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    write_state(
        workspace,
        pid=1234,
        listen_host="127.0.0.1",
        listen_port=8791,
        agent_path="/v1/agent",
        bound_workspace=workspace,
        start_id="start-abc",
    )
    state = read_state(workspace)
    assert state is not None
    assert state["pid"] == 1234
    assert state["listen_host"] == "127.0.0.1"
    assert state["listen_port"] == 8791
    assert state["agent_path"] == "/v1/agent"
    assert state["workspace"] == str(workspace.resolve())
    assert state["start_id"] == "start-abc"
    assert "started_at" in state
    assert state_path(workspace).is_file()


def test_write_state_normalizes_agent_path_without_leading_slash(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    write_state(
        workspace,
        pid=1,
        listen_host="127.0.0.1",
        listen_port=8791,
        agent_path="v1/custom",
        bound_workspace=workspace,
    )
    state = read_state(workspace)
    assert state is not None
    assert state["agent_path"] == "/v1/custom"


def test_clear_state_removes_file(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    write_state(
        workspace,
        pid=1,
        listen_host="127.0.0.1",
        listen_port=8791,
        agent_path=DEFAULT_AGENT_PATH,
        bound_workspace=workspace,
    )
    assert read_state(workspace) is not None
    clear_state(workspace)
    assert read_state(workspace) is None
    assert not state_path(workspace).is_file()


def test_bridge_http_url_and_health_base_url() -> None:
    state = {
        "listen_host": "10.0.0.5",
        "listen_port": 9000,
        "agent_path": "/v1/agent",
    }
    assert bridge_health_base_url(state) == "http://10.0.0.5:9000"
    assert bridge_http_url(state) == "http://10.0.0.5:9000/v1/agent"


def test_bridge_http_url_adds_leading_slash_to_agent_path() -> None:
    state = {"listen_host": "127.0.0.1", "listen_port": 1, "agent_path": "v1/x"}
    assert bridge_http_url(state) == "http://127.0.0.1:1/v1/x"


@pytest.mark.parametrize("alive", [True, False])
def test_bridge_is_running_reflects_pid_alive(tmp_path: Path, alive: bool) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    if alive:
        write_state(
            workspace,
            pid=999,
            listen_host="127.0.0.1",
            listen_port=8791,
            agent_path=DEFAULT_AGENT_PATH,
            bound_workspace=workspace,
        )
    with patch("foundry_cli.bridge.discovery.pid_alive", return_value=alive):
        assert bridge_is_running(workspace) is alive


def test_bridge_is_running_false_without_state(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    with patch("foundry_cli.bridge.discovery.pid_alive", return_value=True):
        assert bridge_is_running(workspace) is False
