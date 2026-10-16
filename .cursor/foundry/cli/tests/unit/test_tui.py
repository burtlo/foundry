"""Unit tests for Foundry Textual TUI (host client helpers and headless smoke)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from foundry_cli.tui.host_client import HostClient, gate_options, open_clarifying_questions

_FIXTURE_MARKDOWN = "# Steward context\n\nFixture paragraph for headless TUI tests."
_DEMO_RUN_ID = "demo-run"


def _mock_run_detail_client(client: MagicMock) -> None:
    client.get_run.return_value = {
        "ok": True,
        "run_id": _DEMO_RUN_ID,
        "status": "running",
        "revision": 1,
        "active_node_id": "shape.present.gate",
        "wait_kind": "decision",
    }
    client.run_context_markdown.return_value = {
        "ok": True,
        "markdown": _FIXTURE_MARKDOWN,
        "revision": 1,
    }
    client.run_context_json.return_value = {"ok": True, "context": {}}
    client.run_events.return_value = {"ok": True, "events": []}


def _mock_run_list_client(client: MagicMock) -> None:
    client.running.return_value = True
    client.list_runs.return_value = {
        "ok": True,
        "runs": [
            {
                "run_id": _DEMO_RUN_ID,
                "status": "running",
                "active_node_id": "shape.present.gate",
                "wait_kind": "decision",
                "revision": 3,
            }
        ],
    }
    _mock_run_detail_client(client)


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


def test_interactive_attach_opens_run_list() -> None:
    pytest.importorskip("textual")
    from foundry_cli.tui.app import FoundryTuiApp, RunListScreen

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    client.list_runs.return_value = {"ok": True, "runs": []}

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=None)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.2)
            assert isinstance(app.screen, RunListScreen)

    asyncio.run(_exercise())


def test_interactive_attach_opens_run_detail() -> None:
    pytest.importorskip("textual")
    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    client.get_run.return_value = {
        "ok": True,
        "run_id": "demo-run",
        "status": "running",
        "revision": 1,
        "active_node_id": "shape.present.gate",
        "wait_kind": "decision",
    }
    client.run_context_markdown.return_value = {"ok": True, "markdown": "# Context"}
    client.run_context_json.return_value = {"ok": True, "context": {}}
    client.run_events.return_value = {"ok": True, "events": []}

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id="demo-run")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.3)
            assert isinstance(app.screen, RunDetailScreen)
            assert app.screen.run_id == "demo-run"

    asyncio.run(_exercise())


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


def test_run_list_row_selected_opens_run_detail() -> None:
    pytest.importorskip("textual")
    from textual.widgets import DataTable

    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen, RunListScreen

    client = MagicMock(spec=HostClient)
    _mock_run_list_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.3)
            assert isinstance(app.screen, RunListScreen)
            table = app.screen.query_one("#run-table", DataTable)
            table.post_message(DataTable.RowSelected(table, cursor_row=0, row_key=table.ordered_rows[0]))
            await pilot.pause(delay=0.1)
            assert isinstance(app.screen, RunDetailScreen)
            assert app.screen.run_id == _DEMO_RUN_ID

    asyncio.run(_exercise())


def test_run_list_enter_opens_run_detail() -> None:
    """AC 27: Enter on the focused row opens run view (pointer covered by RowSelected)."""
    pytest.importorskip("textual")
    from textual.widgets import DataTable

    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen, RunListScreen

    client = MagicMock(spec=HostClient)
    _mock_run_list_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.3)
            assert isinstance(app.screen, RunListScreen)
            table = app.screen.query_one("#run-table", DataTable)
            assert table.row_count == 1
            table.focus()
            await pilot.press("enter")
            await pilot.pause(delay=0.15)
            assert isinstance(app.screen, RunDetailScreen)
            assert app.screen.run_id == _DEMO_RUN_ID

    asyncio.run(_exercise())


def test_run_detail_shows_fixture_context_markdown() -> None:
    pytest.importorskip("textual")
    from textual.widgets import Markdown

    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    _mock_run_detail_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.4)
            assert isinstance(app.screen, RunDetailScreen)
            markdown = app.screen.query_one("#context-markdown", Markdown)
            assert markdown.source == _FIXTURE_MARKDOWN

    asyncio.run(_exercise())


def test_run_detail_escape_returns_to_run_list_without_quit() -> None:
    pytest.importorskip("textual")
    from textual.widgets import DataTable

    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen, RunListScreen

    client = MagicMock(spec=HostClient)
    _mock_run_list_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.3)
            table = app.screen.query_one("#run-table", DataTable)
            table.post_message(DataTable.RowSelected(table, cursor_row=0, row_key=table.ordered_rows[0]))
            await pilot.pause(delay=0.2)
            assert isinstance(app.screen, RunDetailScreen)
            await pilot.press("escape")
            await pilot.pause(delay=0.1)
            assert isinstance(app.screen, RunListScreen)
            assert app.screen_stack[-1] is app.screen

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
        async with app.run_test(size=(100, 30)) as pilot:
            await app.mount(screen)
            screen._rebuild_wait_panel(
                {
                    "wait_kind": "decision",
                    "active_node_id": "execute.start",
                    "revision": 5,
                },
                context=None,
            )
            await pilot.pause(delay=0.2)
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
        async with app.run_test(size=(100, 30)) as pilot:
            await app.mount(screen)
            screen._rebuild_wait_panel(
                {
                    "wait_kind": "decision",
                    "active_node_id": "shape.present.gate",
                },
                context={"produces": {"options": ["accept", "reject"]}},
            )
            await pilot.pause(delay=0.2)
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
        async with app.run_test(size=(100, 30)) as pilot:
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
            await pilot.pause(delay=0.2)
            assert "q1" in screen._answer_inputs
            fields = screen.query(Input)
            assert any(field.id == "answer-q1" for field in fields)
            assert screen.query_one("#submit-answers") is not None

    asyncio.run(_exercise())


def test_wait_panel_rebuild_twice_keeps_unique_advance_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: refresh after advance must await remove_children before remounting."""
    pytest.importorskip("textual")
    from foundry_cli.tui.app import RunDetailScreen

    monkeypatch.setattr(RunDetailScreen, "on_mount", lambda self: None)

    client = MagicMock(spec=HostClient)
    screen = RunDetailScreen(client, "run-1")

    async def _exercise() -> None:
        from textual.app import App

        app = App()
        async with app.run_test(size=(100, 30)) as pilot:
            await app.mount(screen)
            payload = {
                "wait_kind": None,
                "active_node_id": "shape.some.node",
                "revision": 2,
            }
            screen._rebuild_wait_panel(payload)
            await pilot.pause(delay=0.2)
            assert len(screen.query("#advance-btn")) == 1
            payload["revision"] = 3
            screen._rebuild_wait_panel(payload)
            await pilot.pause(delay=0.2)
            assert len(screen.query("#advance-btn")) == 1

    asyncio.run(_exercise())
