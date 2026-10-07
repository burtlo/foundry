"""Host log reading and ``foundry host logs`` command."""

from __future__ import annotations

import argparse
from pathlib import Path

from foundry_cli.host.log_reader import read_log_tail
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
    )
    result = cmd_host_logs(args)
    assert result.get("ok") is True
    assert result.get("lines") == ["alpha", "beta"]
