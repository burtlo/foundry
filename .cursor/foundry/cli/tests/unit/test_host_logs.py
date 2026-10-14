"""Host log reading and ``foundry host logs`` command."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from foundry_cli.host.discovery import write_state
from foundry_cli.host.log_reader import (
    append_host_start_marker,
    follow_log,
    format_host_start_marker,
    read_log_since_marker,
    read_log_tail,
)
from foundry_cli.host.logging_config import configure_host_logging
from foundry_cli.host.paths import host_log_path
from foundry_cli.host_commands import cmd_host_logs


def test_read_log_tail_returns_last_lines(tmp_path: Path) -> None:
    path = tmp_path / "host.log"
    path.write_text("line1\nline2\nline3\n", encoding="utf-8")
    assert read_log_tail(path, max_lines=2) == ["line2", "line3"]


def test_configure_host_logging_writes_file(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    configure_host_logging(workspace, level="INFO")
    log_path = host_log_path(workspace)
    assert log_path.is_file()
    text = log_path.read_text(encoding="utf-8")
    assert "Host logging configured" in text


def test_cmd_host_logs_json(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    (workspace / ".foundry").mkdir()
    log = host_log_path(workspace)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("alpha\nbeta\n", encoding="utf-8")

    args = argparse.Namespace(
        workspace=str(workspace),
        registry=None,
        json=True,
        source="host",
        lines=10,
        follow=False,
        since_start=False,
    )
    result = cmd_host_logs(args)
    assert result.get("ok") is True
    assert result.get("lines") == ["alpha", "beta"]


def test_read_log_since_marker_uses_start_id_line(tmp_path: Path) -> None:
    path = tmp_path / "host.log"
    first_id = "11111111-1111-1111-1111-111111111111"
    second_id = "22222222-2222-2222-2222-222222222222"
    path.write_text(
        "\n".join(
            [
                "stale failure from prior attempt",
                format_host_start_marker(first_id, "2020-01-01T00:00:00Z"),
                "first-run line",
                format_host_start_marker(second_id, "2020-06-01T12:00:00Z"),
                "current-run line",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    lines = read_log_since_marker(
        path,
        marker_timestamp="2020-06-01T12:00:00Z",
        start_id=second_id,
        max_lines=50,
    )
    assert "stale failure" not in "\n".join(lines)
    assert "first-run line" not in lines
    assert lines[0].startswith("FOUNDRY_HOST_START")
    assert lines[-1] == "current-run line"


def test_cmd_host_logs_default_scoped_to_latest_start(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    log = host_log_path(workspace)
    log.parent.mkdir(parents=True, exist_ok=True)
    start_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    marker_at = "2025-03-01T10:00:00Z"
    append_host_start_marker(log, "old-start-id", "2020-01-01T00:00:00Z")
    log.write_text(
        log.read_text(encoding="utf-8")
        + "old error line\n"
        + format_host_start_marker(start_id, marker_at)
        + "\nnew startup line\n",
        encoding="utf-8",
    )
    write_state(
        workspace,
        pid=4242,
        transport="tcp",
        address="127.0.0.1",
        port=9999,
        start_id=start_id,
        start_marker_at=marker_at,
    )

    args = argparse.Namespace(
        workspace=str(workspace),
        registry=None,
        json=False,
        source="host",
        lines=50,
        follow=False,
        since_start=False,
    )
    result = cmd_host_logs(args)
    assert result.get("ok") is True
    out = capsys.readouterr().out
    assert "log=" in out and "pid=4242" in out and "read_at=" in out
    assert "old error line" not in out
    assert "new startup line" in out


def test_cmd_host_logs_since_start_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    log = host_log_path(workspace)
    log.parent.mkdir(parents=True, exist_ok=True)
    start_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    marker_at = "2025-04-01T08:00:00Z"
    log.write_text(
        "pre-marker noise\n"
        + format_host_start_marker(start_id, marker_at)
        + "\npost-marker ok\n",
        encoding="utf-8",
    )
    write_state(
        workspace,
        pid=1,
        transport="tcp",
        address="127.0.0.1",
        port=1,
        start_id=start_id,
        start_marker_at=marker_at,
    )

    args = argparse.Namespace(
        workspace=str(workspace),
        registry=None,
        json=True,
        source="host",
        lines=50,
        follow=False,
        since_start=True,
    )
    result = cmd_host_logs(args)
    assert result.get("ok") is True
    assert result.get("lines") == [
        format_host_start_marker(start_id, marker_at),
        "post-marker ok",
    ]


def test_follow_log_scoped_initial_lines(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Initial follow batch omits pre-marker lines (streaming loop not exercised)."""
    from unittest.mock import patch

    path = tmp_path / "host.log"
    start_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    marker_at = "2025-05-02T09:00:00Z"
    path.write_text(
        "noise before\n"
        + format_host_start_marker(start_id, marker_at)
        + "\nvisible line\n",
        encoding="utf-8",
    )

    with patch("foundry_cli.host.log_reader.time.sleep", side_effect=KeyboardInterrupt):
        try:
            follow_log(
                path,
                max_lines=50,
                marker_timestamp=marker_at,
                start_id=start_id,
            )
        except KeyboardInterrupt:
            pass
    out = capsys.readouterr().out
    assert "noise before" not in out
    assert "visible line" in out


def test_cmd_host_logs_follow_header_and_scoped_follow(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from unittest.mock import MagicMock, patch

    workspace = tmp_path / "app"
    workspace.mkdir()
    log = host_log_path(workspace)
    log.parent.mkdir(parents=True, exist_ok=True)
    start_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    marker_at = "2025-05-01T11:00:00Z"
    log.write_text(
        "pre-marker noise\n"
        + format_host_start_marker(start_id, marker_at)
        + "\npost-marker line\n",
        encoding="utf-8",
    )
    write_state(
        workspace,
        pid=7777,
        transport="tcp",
        address="127.0.0.1",
        port=8888,
        start_id=start_id,
        start_marker_at=marker_at,
    )

    args = argparse.Namespace(
        workspace=str(workspace),
        registry=None,
        json=False,
        source="host",
        lines=50,
        follow=True,
        since_start=False,
    )
    follow_mock = MagicMock(side_effect=KeyboardInterrupt)

    with patch("foundry_cli.host_commands.follow_log", follow_mock):
        result = cmd_host_logs(args)

    assert result.get("ok") is True
    assert result.get("detached") is True
    out = capsys.readouterr().out
    assert "log=" in out and "pid=7777" in out
    follow_mock.assert_called_once()
    _, kwargs = follow_mock.call_args
    assert kwargs.get("start_id") == start_id
    assert kwargs.get("marker_timestamp") == marker_at


def test_cmd_host_start_appends_marker_on_success(tmp_path: Path) -> None:
    from unittest.mock import MagicMock, patch

    from foundry_cli.host.discovery import clear_state, read_state
    from foundry_cli.host_commands import cmd_host_start
    from tests.conftest import FOUNDRY_ROOT

    bundle = FOUNDRY_ROOT
    workspace = tmp_path / "app"
    workspace.mkdir()
    import shutil

    shutil.copytree(
        bundle / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    log = host_log_path(workspace)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("prior attempt noise\n", encoding="utf-8")

    host_state = {
        "pid": 52525,
        "transport": "tcp",
        "address": "127.0.0.1:19001",
        "port": 19001,
    }
    running = {"value": False}

    def _host_is_running(_workspace: Path) -> bool:
        return running["value"]

    def _flip_running_after_spawn(*_args: object, **_kwargs: object) -> MagicMock:
        running["value"] = True
        proc = MagicMock()
        proc.pid = 52525
        return proc

    args = argparse.Namespace(
        workspace=str(workspace),
        registry=str(bundle),
        json=True,
        skip_preflight=True,
        auto_advance=False,
        auto_advance_interval=None,
        _host_spawn_env={},
    )

    try:
        with patch("foundry_cli.host_commands.host_is_running", side_effect=_host_is_running):
            with patch("foundry_cli.host_commands._spawn_detached", side_effect=_flip_running_after_spawn):
                with patch("foundry_cli.host_commands.read_state", return_value=host_state):
                    result = cmd_host_start(args)

        assert result.get("ok") is True
        assert result.get("started") is True
        returned_start_id = result.get("start_id")
        assert returned_start_id

        text = log.read_text(encoding="utf-8")
        assert "FOUNDRY_HOST_START" in text
        assert f"start_id={returned_start_id}" in text

        state = read_state(workspace)
        assert state is not None
        assert state.get("start_id") == returned_start_id
        assert state.get("start_marker_at")
    finally:
        clear_state(workspace)
