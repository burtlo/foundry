"""Unit tests for Foundry Textual TUI (host client helpers and headless smoke)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from foundry_cli.tui.host_client import HostClient, gate_options, open_clarifying_questions

_FIXTURE_OPERATOR_HISTORY = (
    "## What you submitted\n\nFixture intake for headless TUI tests.\n"
)
_STEWARD_EXAMINATION_FIXTURE = (
    "## Position\n\nP19-steward position block.\n\n"
    "## Examination\n\nP19-steward examination body.\n"
)
_DEMO_RUN_ID = "demo-run"
_FOUNDRY_REPO_ROOT = Path(__file__).resolve().parents[5]

_INTAKE_MARKER = "P18-intake: rate limits on the public REST API"
_MODEL_MARKER = "P18-model: examination recommends versioning before rollout"
_LONG_Q1 = (
    "P18-q1: Which API surface should rate limits apply to first — "
    "legacy REST v1, current REST v2, GraphQL gateway, or all of the above?"
)
_LONG_Q2 = (
    "P18-q2: What burst multiplier should we allow for authenticated partners "
    "during maintenance windows without tripping global throttles?"
)
_LONG_Q3 = (
    "P18-q3: Should per-tenant overrides be editable in the admin console or "
    "only via infrastructure-as-code pull requests reviewed by platform?"
)
_APPROVAL_HISTORY = (
    f"## What you submitted\n\n{_INTAKE_MARKER}\n\n"
    f"## What the model concluded\n\n{_MODEL_MARKER}\n\n"
    "## Current step\n\nApprove plan presentation\n\n"
    "# Plan presentation\n\nShip rate limits on REST v2.\n"
)
_AGENT_HISTORY = f"## What you submitted\n\n{_INTAKE_MARKER}\n\n## What the model concluded\n\n{_MODEL_MARKER}\n"


def _label_plain(label: object) -> str:
    content = getattr(label, "content", None)
    if content is not None:
        return str(content)
    renderable = getattr(label, "renderable", "")
    if hasattr(renderable, "plain"):
        return str(renderable.plain)
    return str(renderable)


def _static_plain(widget: object) -> str:
    content = getattr(widget, "content", None)
    if content is not None:
        return str(content)
    renderable = getattr(widget, "renderable", "")
    if renderable is None:
        return ""
    if hasattr(renderable, "plain"):
        return str(renderable.plain)
    return str(renderable)


def _widget_tree_plain(widget: object) -> str:
    parts = [_static_plain(widget)]
    query = getattr(widget, "query", None)
    if callable(query):
        from textual.widgets import Static

        for child in query(Static):
            parts.append(_static_plain(child))
    return " ".join(part for part in parts if part)


def _technical_markdown_visible(screen: object) -> bool:
    from textual.widgets import Markdown

    tech = screen.query_one("#technical-markdown", Markdown)
    return tech.has_class("-visible")


def _visible_technical_source(screen: object) -> str:
    from textual.widgets import Markdown

    tech = screen.query_one("#technical-markdown", Markdown)
    if not _technical_markdown_visible(screen):
        return ""
    return tech.source or ""


def _footer_plain(screen: object) -> str:
    from textual.widgets import Footer

    footer = screen.query_one(Footer)
    parts: list[str] = []
    for key_widget in footer.query("FooterKey"):
        parts.append(str(key_widget.render()))
    return " ".join(parts)


def _is_descendant_of(widget: object, ancestor: object) -> bool:
    node = widget
    while node is not None:
        if node is ancestor:
            return True
        node = getattr(node, "parent", None)
    return False


def _mock_three_question_user_input_client(client: MagicMock) -> None:
    client.workspace = _FOUNDRY_REPO_ROOT
    client.registry = None
    client.running.return_value = True
    client.get_run.return_value = {
        "ok": True,
        "run_id": _DEMO_RUN_ID,
        "status": "running",
        "revision": 2,
        "active_node_id": "shape.examine",
        "wait_kind": "user_input",
    }
    client.run_operator_history_markdown.return_value = {
        "ok": True,
        "markdown": (
            f"## What you submitted\n\n{_INTAKE_MARKER}\n\n"
            f"## What the model concluded\n\n{_MODEL_MARKER}\n"
        ),
        "revision": 2,
    }
    client.run_context_json.return_value = {
        "ok": True,
        "context": {
            "reads": {
                "state": {
                    "clarifying_questions": [
                        {"id": "q1", "text": _LONG_Q1, "status": "open"},
                        {"id": "q2", "text": _LONG_Q2, "status": "open"},
                        {"id": "q3", "text": _LONG_Q3, "status": "open"},
                    ]
                }
            }
        },
    }
    client.run_events.return_value = {"ok": True, "events": []}


def _mock_approval_client(client: MagicMock) -> None:
    client.workspace = _FOUNDRY_REPO_ROOT
    client.registry = None
    client.running.return_value = True
    client.get_run.return_value = {
        "ok": True,
        "run_id": _DEMO_RUN_ID,
        "status": "running",
        "revision": 5,
        "active_node_id": "shape.present.gate",
        "wait_kind": "decision",
    }
    client.run_operator_history_markdown.return_value = {
        "ok": True,
        "markdown": _APPROVAL_HISTORY,
        "revision": 5,
    }
    client.run_context_json.return_value = {
        "ok": True,
        "context": {"produces": {"options": ["accept", "reject"]}},
    }
    client.run_events.return_value = {"ok": True, "events": []}


def _mock_agent_wait_client(client: MagicMock) -> None:
    client.workspace = _FOUNDRY_REPO_ROOT
    client.registry = None
    client.running.return_value = True
    client.get_run.return_value = {
        "ok": True,
        "run_id": _DEMO_RUN_ID,
        "status": "running",
        "revision": 3,
        "phase": "shape",
        "active_visit_id": "visit-agent-1",
        "active_node_id": "shape.examine",
        "wait_kind": "agent",
    }
    client.run_operator_history_markdown.return_value = {
        "ok": True,
        "markdown": _AGENT_HISTORY,
        "revision": 3,
    }
    client.run_context_json.return_value = {"ok": True, "context": {}}
    client.run_events.return_value = {"ok": True, "events": []}


def _mock_run_detail_client(client: MagicMock) -> None:
    client.workspace = _FOUNDRY_REPO_ROOT
    client.registry = None
    client.get_run.return_value = {
        "ok": True,
        "run_id": _DEMO_RUN_ID,
        "status": "running",
        "revision": 1,
        "phase": "shape",
        "active_visit_id": "visit-approval-1",
        "active_node_id": "shape.present.gate",
        "wait_kind": "decision",
    }
    client.run_operator_history_markdown.return_value = {
        "ok": True,
        "markdown": _FIXTURE_OPERATOR_HISTORY,
        "revision": 1,
    }
    client.run_context_markdown.return_value = {
        "ok": True,
        "markdown": _STEWARD_EXAMINATION_FIXTURE,
        "revision": 1,
    }
    client.run_context_json.return_value = {"ok": True, "context": {}}
    client.run_events.return_value = {"ok": True, "events": []}


def _mock_run_list_client(client: MagicMock) -> None:
    client.workspace = _FOUNDRY_REPO_ROOT
    client.registry = None
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


def test_needs_label_maps_wait_kinds() -> None:
    from foundry_cli.run_labels import needs_label

    assert needs_label("user_input") == "Answers"
    assert needs_label("decision") == "Approval"
    assert needs_label("agent") == "Agent"
    assert needs_label("operator") == "Action"
    assert needs_label(None) == "—"
    assert needs_label("") == "—"
    assert needs_label("custom_wait") == "Custom Wait"


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
    client.run_operator_history_markdown.return_value = {
        "ok": True,
        "markdown": _FIXTURE_OPERATOR_HISTORY,
        "revision": 1,
    }
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


def test_run_list_human_columns_and_needs_labels() -> None:
    """AC 25: operator run-list columns and Needs labels."""
    pytest.importorskip("textual")
    from textual.widgets import DataTable

    from foundry_cli.run_labels import load_operator_flow, node_step_title
    from foundry_cli.tui.app import FoundryTuiApp, RunListScreen

    flow = load_operator_flow(_FOUNDRY_REPO_ROOT)
    assert flow is not None
    present_title = node_step_title("shape.present.gate", flow)
    examine_title = node_step_title("shape.examine", flow)

    client = MagicMock(spec=HostClient)
    client.workspace = _FOUNDRY_REPO_ROOT
    client.registry = None
    client.running.return_value = True
    client.list_runs.return_value = {
        "ok": True,
        "runs": [
            {
                "run_id": "run-answers",
                "active_node_id": "shape.examine",
                "wait_kind": "user_input",
            },
            {
                "run_id": "run-approval",
                "active_node_id": "shape.present.gate",
                "wait_kind": "decision",
            },
            {
                "run_id": "run-agent",
                "active_node_id": "shape.examine",
                "wait_kind": "agent",
            },
            {
                "run_id": "run-idle",
                "active_node_id": "shape.examine",
                "wait_kind": None,
            },
        ],
    }

    async def _exercise() -> None:
        app = FoundryTuiApp(client)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.3)
            assert isinstance(app.screen, RunListScreen)
            table = app.screen.query_one("#run-table", DataTable)
            headers = [column.label.plain for column in table.columns.values()]
            assert headers == ["Run ID", "Status", "Current step", "Needs"]
            assert table.row_count == 4
            assert list(table.get_row_at(0)) == [
                "run-answers",
                "—",
                examine_title,
                "Answers",
            ]
            assert list(table.get_row_at(1)) == [
                "run-approval",
                "—",
                present_title,
                "Approval",
            ]
            assert list(table.get_row_at(2)) == ["run-agent", "—", examine_title, "Agent"]
            assert list(table.get_row_at(3)) == ["run-idle", "—", examine_title, "—"]
            assert "shape.examine" not in examine_title

    asyncio.run(_exercise())


def test_run_list_and_detail_surface_halted_status() -> None:
    """Halted runs show Status: Halted in list and run header."""
    pytest.importorskip("textual")
    from textual.widgets import DataTable, Static

    from foundry_cli.run_labels import load_operator_flow, node_step_title
    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen, RunListScreen

    flow = load_operator_flow(_FOUNDRY_REPO_ROOT)
    assert flow is not None
    intake_title = node_step_title("execute.intake", flow)

    client = MagicMock(spec=HostClient)
    client.workspace = _FOUNDRY_REPO_ROOT
    client.registry = None
    client.running.return_value = True
    client.list_runs.return_value = {
        "ok": True,
        "runs": [
            {
                "run_id": "foundry-0002",
                "status": "halted",
                "active_node_id": "execute.intake",
                "wait_kind": None,
            }
        ],
    }
    client.get_run.return_value = {
        "ok": True,
        "run_id": "foundry-0002",
        "status": "halted",
        "revision": 19,
        "active_node_id": "execute.intake",
        "wait_kind": None,
    }
    client.run_operator_history_markdown.return_value = {
        "ok": True,
        "markdown": _FIXTURE_OPERATOR_HISTORY,
        "revision": 19,
    }
    client.run_events.return_value = {"ok": True, "events": []}

    async def _exercise() -> None:
        app = FoundryTuiApp(client)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.3)
            assert isinstance(app.screen, RunListScreen)
            table = app.screen.query_one("#run-table", DataTable)
            assert list(table.get_row_at(0)) == [
                "foundry-0002",
                "Halted",
                intake_title,
                "—",
            ]
            app.screen._open_run_row(0)
            await pilot.pause(delay=0.4)
            screen = app.screen
            assert isinstance(screen, RunDetailScreen)
            summary = _static_plain(screen.query_one("#run-summary", Static))
            assert "Status: Halted" in summary
            assert intake_title in summary
            assert "Needs: —" in summary

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
    from textual.containers import VerticalScroll
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
            assert len(app.screen.query("#actions-panel")) == 0
            scroll = app.screen.query_one("#run-scroll", VerticalScroll)
            assert scroll is not None
            markdown = app.screen.query_one("#context-markdown", Markdown)
            assert markdown.source == _FIXTURE_OPERATOR_HISTORY
            client.run_operator_history_markdown.assert_called()

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
    from textual.widgets import Markdown, TextArea

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
            fields = screen.query(TextArea)
            assert any(field.id == "answer-q1" for field in fields)
            assert screen.query_one("#submit-answers") is not None
            wait_panel = screen.query_one("#wait-panel")
            question_md = " ".join(
                (widget.source or "") for widget in wait_panel.query(Markdown)
            )
            assert "Which API?" in question_md
            assert "(q1)" in question_md

    asyncio.run(_exercise())


def test_wait_panel_rebuild_twice_keeps_unique_submit_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: refresh must await remove_children before remounting wait controls."""
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
            payload = {"wait_kind": "user_input", "active_node_id": "shape.examine"}
            context = {
                "reads": {
                    "state": {
                        "clarifying_questions": [
                            {"id": "q1", "text": "Which API?", "status": "open"},
                        ]
                    }
                }
            }
            screen._rebuild_wait_panel(payload, context=context)
            await pilot.pause(delay=0.2)
            assert len(screen.query("#submit-answers")) == 1
            payload["revision"] = 3
            screen._rebuild_wait_panel(payload, context=context)
            await pilot.pause(delay=0.2)
            assert len(screen.query("#submit-answers")) == 1

    asyncio.run(_exercise())


def test_run_detail_initial_focus_main_panel_shift_tab_tech_toggle() -> None:
    """Run view opens with #run-scroll focused; Shift+Tab reaches technical context."""
    pytest.importorskip("textual")
    from textual.containers import VerticalScroll
    from textual.widgets import Button

    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    client = MagicMock(spec=HostClient)
    _mock_three_question_user_input_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(delay=0.6)
            screen = app.screen
            assert isinstance(screen, RunDetailScreen)
            assert isinstance(app.focused, VerticalScroll)
            assert app.focused.id == "run-scroll"

            scroll = screen.query_one("#run-scroll", VerticalScroll)
            await pilot.press("down")
            await pilot.pause(delay=0.05)
            assert scroll.scroll_y > 0

            await pilot.press("shift+tab")
            await pilot.pause(delay=0.05)
            toggle = screen.query_one("#toggle-tech-context", Button)
            assert app.focused is toggle

    asyncio.run(_exercise())


def test_run_detail_single_scroll_no_actions_panel() -> None:
    """P18: history and action share #run-scroll; side rail removed."""
    pytest.importorskip("textual")
    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    client = MagicMock(spec=HostClient)
    _mock_run_detail_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(delay=0.4)
            assert isinstance(app.screen, RunDetailScreen)
            assert len(app.screen.query("#actions-panel")) == 0
            assert app.screen.query_one("#run-scroll") is not None

    asyncio.run(_exercise())


def test_run_detail_user_input_three_questions_at_80x24() -> None:
    """P18 / AC 29: 80×24 user_input — top of history, full-width inputs in #run-scroll."""
    pytest.importorskip("textual")
    from textual.containers import VerticalScroll
    from textual.widgets import Markdown, TextArea

    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    client = MagicMock(spec=HostClient)
    _mock_three_question_user_input_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(delay=0.5)
            screen = app.screen
            assert isinstance(screen, RunDetailScreen)
            assert len(screen.query("#actions-panel")) == 0

            scroll = screen.query_one("#run-scroll", VerticalScroll)
            assert scroll.scroll_y == 0

            markdown = screen.query_one("#context-markdown", Markdown)
            history = markdown.source or ""
            assert _INTAKE_MARKER in history
            assert _MODEL_MARKER in history
            assert _LONG_Q1 not in history
            assert "## Questions and answers" not in history

            wait_panel = screen.query_one("#wait-panel")
            assert _is_descendant_of(wait_panel, scroll)
            assert "Questions and answers" in _widget_tree_plain(wait_panel)
            answer_fields = list(wait_panel.query(TextArea))
            assert len(answer_fields) == 3
            for field in answer_fields:
                assert _is_descendant_of(field, scroll)
                assert field.size.height >= 3

            question_md = " ".join(
                (widget.source or "") for widget in wait_panel.query(Markdown)
            )
            assert _LONG_Q1 in question_md
            assert _LONG_Q2 in question_md
            assert _LONG_Q3 in question_md
            assert "*(q1)*" in question_md

    asyncio.run(_exercise())


def test_run_detail_approval_history_before_controls() -> None:
    """P18: approval material in history markdown; decision controls follow in scroll."""
    pytest.importorskip("textual")
    from textual.containers import VerticalScroll
    from textual.widgets import Markdown

    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    client = MagicMock(spec=HostClient)
    _mock_approval_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(delay=0.5)
            screen = app.screen
            assert isinstance(screen, RunDetailScreen)
            scroll = screen.query_one("#run-scroll", VerticalScroll)
            markdown = screen.query_one("#context-markdown", Markdown)
            history = markdown.source or ""
            assert "Ship rate limits on REST v2." in history
            assert "Approve plan presentation" in history

            decide = screen.query_one("#decide-opt-0")
            assert _is_descendant_of(decide, scroll)
            assert history.index(_INTAKE_MARKER) < history.index("Ship rate limits")
            assert _is_descendant_of(markdown, scroll)
            children = list(scroll.children)
            md_index = children.index(markdown)
            wait_index = children.index(screen.query_one("#wait-panel"))
            assert md_index < wait_index

    asyncio.run(_exercise())


def test_run_detail_agent_wait_empty_panel() -> None:
    """P18 / AC 36: non-human agent wait — no answer or approval controls."""
    pytest.importorskip("textual")
    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    client = MagicMock(spec=HostClient)
    _mock_agent_wait_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(delay=0.5)
            screen = app.screen
            assert isinstance(screen, RunDetailScreen)
            assert len(screen.query("#submit-answers")) == 0
            assert len(screen.query("#decide-opt-0")) == 0
            assert len(screen.query("#decide-custom")) == 0
            assert len(screen.query("#start-btn")) == 0
            wait_panel = screen.query_one("#wait-panel")
            assert len(list(wait_panel.children)) == 0

    asyncio.run(_exercise())


def test_run_detail_history_refresh_preserves_scroll_y() -> None:
    """P18 / D21: second operator-history update keeps the operator's scroll offset."""
    pytest.importorskip("textual")
    from textual.containers import VerticalScroll
    from textual.widgets import Markdown

    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    client = MagicMock(spec=HostClient)
    _mock_three_question_user_input_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(delay=0.5)
            screen = app.screen
            assert isinstance(screen, RunDetailScreen)
            scroll = screen.query_one("#run-scroll", VerticalScroll)
            assert scroll.scroll_y == 0

            scroll.scroll_to(y=42, animate=False)
            await pilot.pause(delay=0.05)
            saved_y = scroll.scroll_y
            assert saved_y > 0

            markdown = screen.query_one("#context-markdown", Markdown)
            screen._apply_context_markdown(
                {
                    "ok": True,
                    "markdown": (
                        f"## What you submitted\n\n{_INTAKE_MARKER}\n\n"
                        f"## What the model concluded\n\n{_MODEL_MARKER}\n\n"
                        "## Updated\n\nSecond history revision.\n"
                    ),
                    "revision": 4,
                }
            )
            await pilot.pause(delay=0.05)
            assert scroll.scroll_y == saved_y

    asyncio.run(_exercise())


def test_run_detail_p19_header_summary_without_steward_on_open() -> None:
    """P19 / AC 33–34: operator header on open; steward headings stay hidden."""
    pytest.importorskip("textual")
    from textual.widgets import Markdown, Static

    from foundry_cli.run_labels import load_operator_flow, node_step_title
    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    flow = load_operator_flow(_FOUNDRY_REPO_ROOT)
    assert flow is not None
    present_title = node_step_title("shape.present.gate", flow)

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    _mock_run_detail_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(delay=0.5)
            screen = app.screen
            assert isinstance(screen, RunDetailScreen)

            summary = _static_plain(screen.query_one("#run-summary", Static))
            assert _DEMO_RUN_ID in summary
            assert present_title in summary
            assert "Status: Running" in summary
            assert "Needs: Approval" in summary
            assert "revision=" not in summary
            assert "shape.present.gate" not in summary

            history = screen.query_one("#context-markdown", Markdown).source or ""
            assert "## Position" not in history
            assert "## Examination" not in history
            assert _visible_technical_source(screen) == ""
            assert not _technical_markdown_visible(screen)
            client.run_context_markdown.assert_not_called()

    asyncio.run(_exercise())


def test_run_detail_p19_technical_context_toggle() -> None:
    """P19 / AC 34: steward packet after wait-panel; toggle removes it."""
    pytest.importorskip("textual")
    from textual.containers import VerticalScroll
    from textual.widgets import Markdown

    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    _mock_run_detail_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(delay=0.5)
            screen = app.screen
            assert isinstance(screen, RunDetailScreen)
            assert "## Examination" not in (screen.query_one("#context-markdown", Markdown).source or "")
            assert _visible_technical_source(screen) == ""

            await pilot.click("#toggle-tech-context")
            await pilot.pause(delay=0.5)

            tech = screen.query_one("#technical-markdown", Markdown)
            assert _technical_markdown_visible(screen)
            tech_text = tech.source or ""
            assert "## Examination" in tech_text
            assert "P19-steward examination body." in tech_text
            assert "**revision:** 1" in tech_text
            assert "**visit id:** visit-approval-1" in tech_text
            assert "**phase:** shape" in tech_text
            assert "`shape.present.gate`" in tech_text

            scroll = screen.query_one("#run-scroll", VerticalScroll)
            wait_panel = screen.query_one("#wait-panel")
            children = list(scroll.children)
            assert children.index(wait_panel) < children.index(tech)

            await pilot.click("#toggle-tech-context")
            await pilot.pause(delay=0.3)
            assert not _technical_markdown_visible(screen)
            assert _visible_technical_source(screen) == ""
            assert (tech.source or "").strip() == ""

    asyncio.run(_exercise())


def test_run_list_footer_includes_help_ctrl_question() -> None:
    """P20 / AC 35: run list footer shows Help Ctrl+? beside Refresh and Quit."""
    pytest.importorskip("textual")
    from foundry_cli.tui.app import FoundryTuiApp, RunListScreen

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    client.list_runs.return_value = {"ok": True, "runs": []}

    async def _exercise() -> None:
        app = FoundryTuiApp(client)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.3)
            assert isinstance(app.screen, RunListScreen)
            footer = _footer_plain(app.screen)
            assert "Help Ctrl+?" in footer
            assert "Refresh" in footer
            assert "Quit" in footer

    asyncio.run(_exercise())


def test_run_list_ctrl_question_opens_help_panel() -> None:
    """P20 / AC 35: Ctrl+? opens help mentioning palette and technical context."""
    pytest.importorskip("textual")
    from foundry_cli.tui.app import FoundryTuiApp, OperatorHelpScreen, RunListScreen

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    client.list_runs.return_value = {"ok": True, "runs": []}

    async def _exercise() -> None:
        app = FoundryTuiApp(client)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.3)
            assert isinstance(app.screen, RunListScreen)
            await pilot.press("ctrl+question_mark")
            await pilot.pause(delay=0.1)
            assert isinstance(app.screen, OperatorHelpScreen)
            help_text = _static_plain(app.screen.query_one("#operator-help-text"))
            assert "Ctrl+P" in help_text
            assert "command palette" in help_text.lower()
            assert "technical context" in help_text.lower()
            await pilot.press("escape")
            await pilot.pause(delay=0.1)
            assert isinstance(app.screen, RunListScreen)

    asyncio.run(_exercise())


def test_run_detail_footer_includes_help_and_back() -> None:
    """P20 / AC 35: run view footer shows Help Ctrl+? and Back."""
    pytest.importorskip("textual")
    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    _mock_run_detail_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.4)
            assert isinstance(app.screen, RunDetailScreen)
            footer = _footer_plain(app.screen)
            assert "Help Ctrl+?" in footer
            assert "Back" in footer
            assert "Refresh" in footer
            assert "Quit" in footer

    asyncio.run(_exercise())


def test_run_detail_ctrl_question_opens_help_panel() -> None:
    """P20 / AC 35: Ctrl+? on run view opens the same help panel."""
    pytest.importorskip("textual")
    from foundry_cli.tui.app import FoundryTuiApp, OperatorHelpScreen, RunDetailScreen

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    _mock_run_detail_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.4)
            assert isinstance(app.screen, RunDetailScreen)
            await pilot.press("ctrl+question_mark")
            await pilot.pause(delay=0.1)
            assert isinstance(app.screen, OperatorHelpScreen)
            help_text = _static_plain(app.screen.query_one("#operator-help-text"))
            assert "Arrow keys" in help_text
            assert "Ctrl+P" in help_text
            assert "technical context" in help_text.lower()

    asyncio.run(_exercise())


def test_ctrl_p_opens_command_palette_from_list_and_run_detail() -> None:
    """P20 / AC 35: Ctrl+P still opens the Textual command palette."""
    pytest.importorskip("textual")
    from textual.command import CommandPalette

    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen, RunListScreen

    client = MagicMock(spec=HostClient)
    client.running.return_value = True
    client.list_runs.return_value = {"ok": True, "runs": []}
    _mock_run_detail_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.3)
            assert isinstance(app.screen, RunListScreen)
            await pilot.press("ctrl+p")
            await pilot.pause(delay=0.1)
            assert isinstance(app.screen, CommandPalette)
            await pilot.press("escape")
            await pilot.pause(delay=0.1)
            assert isinstance(app.screen, RunListScreen)

        app2 = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app2.run_test(size=(100, 30)) as pilot:
            await pilot.pause(delay=0.4)
            assert isinstance(app2.screen, RunDetailScreen)
            await pilot.press("ctrl+p")
            await pilot.pause(delay=0.1)
            assert isinstance(app2.screen, CommandPalette)

    asyncio.run(_exercise())


def test_run_detail_p19_agent_wait_header_needs_agent() -> None:
    """P19 / AC 36: agent wait shows operator header without answer controls."""
    pytest.importorskip("textual")
    from textual.widgets import Static

    from foundry_cli.run_labels import load_operator_flow, node_step_title
    from foundry_cli.tui.app import FoundryTuiApp, RunDetailScreen

    flow = load_operator_flow(_FOUNDRY_REPO_ROOT)
    assert flow is not None
    examine_title = node_step_title("shape.examine", flow)

    client = MagicMock(spec=HostClient)
    _mock_agent_wait_client(client)

    async def _exercise() -> None:
        app = FoundryTuiApp(client, initial_run_id=_DEMO_RUN_ID)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(delay=0.5)
            screen = app.screen
            assert isinstance(screen, RunDetailScreen)
            summary = _static_plain(screen.query_one("#run-summary", Static))
            assert _DEMO_RUN_ID in summary
            assert examine_title in summary
            assert "Status: Running" in summary
            assert "Needs: Agent" in summary
            assert "revision=" not in summary
            assert len(screen.query("#submit-answers")) == 0
            assert len(screen.query("#decide-opt-0")) == 0

    asyncio.run(_exercise())
