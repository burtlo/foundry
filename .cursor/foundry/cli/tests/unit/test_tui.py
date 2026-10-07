"""Unit tests for Foundry Textual TUI (host client helpers and headless smoke)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from foundry_cli.tui.host_client import HostClient, gate_options, open_clarifying_questions


def test_open_clarifying_questions_filters_answered() -> None:
    context = {
        "reads": {
            "state": {
                "clarifying_questions": [
                    {"id": "q1", "text": "A?", "status": "open"},
                    {"id": "q2", "text": "B?", "status": "answered"},
                ]
            }
        }
    }
    open_q = open_clarifying_questions(context)
    assert [item["id"] for item in open_q] == ["q1"]


def test_gate_options_from_context() -> None:
    context = {"produces": {"options": ["accept", "reject"]}}
    assert gate_options(context) == ["accept", "reject"]


def test_host_client_advance_includes_idempotency_key(tmp_path: Path) -> None:
    client = HostClient(tmp_path)
    with patch("foundry_cli.tui.host_client.call_host") as call_host:
        call_host.return_value = {"ok": True, "revision": 2}
        client.advance("run-1", expected_revision=1)
        call_host.assert_called_once()
        method, params = call_host.call_args[0][1], call_host.call_args[0][2]
        assert method == "run.advance"
        assert params["run_id"] == "run-1"
        assert params["expected_revision"] == 1
        assert "idempotency_key" in params


def test_tui_run_list_screen_mounts() -> None:
    pytest.importorskip("textual")
    from foundry_cli.tui.app import FoundryTuiApp, RunListScreen

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    client.list_runs.return_value = {
        "ok": True,
        "runs": [
            {
                "run_id": "demo-run",
                "status": "running",
                "active_node_id": "shape.present.gate",
                "wait_kind": "decision",
                "revision": 3,
            }
        ],
    }

    async def _exercise() -> None:
        app = FoundryTuiApp(client)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.3)
            assert isinstance(app.screen, RunListScreen)
            table = app.screen.query_one("#run-table")
            assert table.row_count == 1

    asyncio.run(_exercise())


def test_wait_panel_execute_start(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")
    from foundry_cli.tui.app import RunDetailScreen

    monkeypatch.setattr(RunDetailScreen, "on_mount", lambda self: None)

    client = MagicMock(spec=HostClient)
    screen = RunDetailScreen(client, "run-1")

    async def _exercise() -> None:
        from textual.app import App

        app = App()
        async with app.run_test(size=(100, 30)):
            await app.mount(screen)
            screen._rebuild_wait_panel(
                {
                    "wait_kind": "decision",
                    "active_node_id": "execute.start",
                    "revision": 5,
                },
                context=None,
            )
            assert screen.query_one("#start-btn") is not None
            assert len(screen.query("#advance-btn")) == 0

    asyncio.run(_exercise())


def test_wait_panel_decision_options(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")
    from foundry_cli.tui.app import RunDetailScreen

    monkeypatch.setattr(RunDetailScreen, "on_mount", lambda self: None)

    client = MagicMock(spec=HostClient)
    screen = RunDetailScreen(client, "run-1")

    async def _exercise() -> None:
        from textual.app import App

        app = App()
        async with app.run_test(size=(100, 30)):
            await app.mount(screen)
            screen._rebuild_wait_panel(
                {
                    "wait_kind": "decision",
                    "active_node_id": "shape.present.gate",
                },
                context={"produces": {"options": ["accept", "reject"]}},
            )
            assert screen._decision_options == ["accept", "reject"]
            assert screen.query_one("#decide-opt-0") is not None
            assert screen.query_one("#decide-custom-btn") is not None

    asyncio.run(_exercise())


def test_wait_panel_user_input_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")
    from foundry_cli.tui.app import RunDetailScreen
    from textual.widgets import Input

    monkeypatch.setattr(RunDetailScreen, "on_mount", lambda self: None)

    client = MagicMock(spec=HostClient)
    screen = RunDetailScreen(client, "run-1")

    async def _exercise() -> None:
        from textual.app import App

        app = App()
        async with app.run_test(size=(100, 30)):
            await app.mount(screen)
            screen._rebuild_wait_panel(
                {"wait_kind": "user_input", "active_node_id": "shape.examine"},
                context={
                    "reads": {
                        "state": {
                            "clarifying_questions": [
                                {"id": "q1", "text": "Which API?", "status": "open"},
                            ]
                        }
                    }
                },
            )
            assert "q1" in screen._answer_inputs
            fields = screen.query(Input)
            assert any(field.id == "answer-q1" for field in fields)
            assert screen.query_one("#submit-answers") is not None

    asyncio.run(_exercise())
