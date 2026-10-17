"""Foundry Textual TUI — host-only operator client."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from textual import on, work
from textual.events import Focus
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Markdown, Static, TextArea

from foundry_cli.operator_history import format_clarifying_question_markdown
from foundry_cli.run_labels import (
    load_operator_flow,
    needs_label,
    node_step_title,
    run_status_label,
)
from foundry_cli.tui.host_client import HostClient, gate_options, open_clarifying_questions

EXECUTE_START_NODE = "execute.start"

OPERATOR_HELP_BINDING = Binding(
    "ctrl+question_mark",
    "show_operator_help",
    "Help Ctrl+?",
    key_display="",
    show=True,
)

_OPERATOR_HELP_TEXT = (
    "Foundry attach — quick help\n\n"
    "Navigation\n"
    "• Arrow keys — move selection in the run list\n"
    "• Enter or click a row — open a run\n\n"
    "Common keys\n"
    "• r — refresh the current screen\n"
    "• q — quit attach\n"
    "• Esc — back to the run list (run view)\n\n"
    "Command palette\n"
    "• Ctrl+P — open the full command palette for all actions\n\n"
    "Run view\n"
    "• Arrow keys — scroll run history when the main panel is focused\n"
    "• Tab — move to answer or decision controls below the history\n"
    "• Shift+Tab — focus Show technical context in the header\n"
    "• Show technical context — steward diagnostics "
    "(revision, visit id, phase, node id)"
)


class OperatorHelpScreen(ModalScreen[None]):
    """Short operator help (Ctrl+?)."""

    DEFAULT_CSS = """
    OperatorHelpScreen {
        align: center middle;
    }
    #operator-help-panel {
        width: 72;
        height: auto;
        max-height: 90%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #operator-help-text {
        height: auto;
        margin-bottom: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="operator-help-panel"):
            yield Static(_OPERATOR_HELP_TEXT, id="operator-help-text")
            yield Button("Close", variant="primary", id="close-operator-help")

    @on(Button.Pressed, "#close-operator-help")
    def _close(self) -> None:
        self.dismiss()

    def action_dismiss(self) -> None:
        self.dismiss()


class OperatorHelpMixin:
    """Shared Ctrl+? help panel action for attach screens."""

    def action_show_operator_help(self) -> None:
        self.app.push_screen(OperatorHelpScreen())


def _run_signature(run_payload: dict[str, Any]) -> tuple[Any, ...]:
    parked = run_payload.get("parked")
    parked_commands: tuple[str, ...] = ()
    if isinstance(parked, dict):
        raw = parked.get("commands")
        if isinstance(raw, list):
            parked_commands = tuple(str(item) for item in raw if item is not None)
    return (
        run_payload.get("revision"),
        run_payload.get("wait_kind"),
        run_payload.get("active_node_id"),
        run_payload.get("status"),
        run_payload.get("phase"),
        parked_commands,
    )


def _parked_record(run_payload: dict[str, Any]) -> dict[str, Any] | None:
    parked = run_payload.get("parked")
    return parked if isinstance(parked, dict) else None


def _parked_commands(run_payload: dict[str, Any]) -> list[str]:
    parked = _parked_record(run_payload)
    if not parked:
        return []
    raw = parked.get("commands")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item is not None]


def _commands_include_advance(commands: list[str]) -> bool:
    return any(line.strip().startswith("foundry run advance ") for line in commands)


def _commands_include_retry(commands: list[str]) -> bool:
    return any(line.strip().startswith("foundry retry ") for line in commands)


def _context_packet(context_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not context_result or not context_result.get("ok"):
        return None
    packet = context_result.get("context")
    return packet if isinstance(packet, dict) else None


def _needs_context_json_for_wait(run_payload: dict[str, Any]) -> bool:
    if _parked_record(run_payload) is None:
        return False
    wait_kind = run_payload.get("wait_kind")
    active_node = str(run_payload.get("active_node_id") or "")
    if active_node == EXECUTE_START_NODE and wait_kind == "decision":
        return False
    return wait_kind in ("decision", "user_input")


class HostPromptScreen(ModalScreen[bool]):
    """Ask the operator to start the job host."""

    DEFAULT_CSS = """
    HostPromptScreen {
        align: center middle;
    }
    #host-prompt {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="host-prompt"):
            yield Static(
                "The Foundry job host is not running.\n"
                "Start it now to use the TUI (host-only client)?",
                id="host-prompt-text",
            )
            with Horizontal():
                yield Button("Start host", variant="primary", id="start-host")
                yield Button("Quit", id="quit-tui")

    @on(Button.Pressed, "#start-host")
    def _start(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#quit-tui")
    def _quit(self) -> None:
        self.dismiss(False)


class RunListScreen(OperatorHelpMixin, Screen):
    """Workspace run list via ``run.list``."""

    BINDINGS: ClassVar[list[Binding]] = [
        OPERATOR_HELP_BINDING,
        Binding("r", "refresh_runs", "Refresh"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self, client: HostClient) -> None:
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Runs — click a row or press Enter to open", id="run-list-title")
        yield DataTable(id="run-table", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#run-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Run ID", "Status", "Current step", "Needs")
        self.action_refresh_runs()

    def action_refresh_runs(self) -> None:
        self._fetch_runs()

    @work(thread=True, exclusive=True)
    def _fetch_runs(self) -> None:
        result = self.client.list_runs()
        self.app.call_from_thread(self._apply_runs, result)

    def _apply_runs(self, result: dict[str, Any]) -> None:
        table = self.query_one("#run-table", DataTable)
        table.clear()
        if not result.get("ok"):
            self.notify(self._error_message(result), severity="error", timeout=8)
            return
        workspace = getattr(self.client, "workspace", None)
        registry = getattr(self.client, "registry", None)
        flow = None
        if isinstance(workspace, Path):
            reg = registry if isinstance(registry, str) else None
            flow = load_operator_flow(workspace, registry=reg)
        for row in result.get("runs") or []:
            if not isinstance(row, dict):
                continue
            wait_kind = row.get("wait_kind")
            if wait_kind is not None and not isinstance(wait_kind, str):
                wait_kind = str(wait_kind)
            table.add_row(
                str(row.get("run_id") or ""),
                run_status_label(row.get("status") if isinstance(row.get("status"), str) else None),
                node_step_title(
                    str(row.get("active_node_id") or "") or None,
                    flow,
                ),
                needs_label(wait_kind),
            )

    @on(DataTable.RowSelected, "#run-table")
    def _on_run_row_selected(self, event: DataTable.RowSelected) -> None:
        self._open_run_row(event.cursor_row)

    def _open_run_row(self, row_index: int | None) -> None:
        table = self.query_one("#run-table", DataTable)
        if table.row_count == 0 or row_index is None:
            return
        run_id = str(table.get_row_at(row_index)[0])
        if not run_id:
            return
        self.app.push_screen(RunDetailScreen(self.client, run_id))

    @staticmethod
    def _error_message(result: dict[str, Any]) -> str:
        err = result.get("error") if isinstance(result.get("error"), dict) else {}
        code = err.get("code") or "ERROR"
        message = err.get("message") or "Request failed"
        return f"[{code}] {message}"


class RunDetailScreen(OperatorHelpMixin, Screen):
    """Run status, wait actions, events, and steward context."""

    BINDINGS: ClassVar[list[Binding]] = [
        OPERATOR_HELP_BINDING,
        Binding("escape", "pop_screen", "Back"),
        Binding("r", "refresh_all", "Refresh"),
        Binding("a", "advance_run", "Advance"),
        Binding("s", "start_execute", "Start"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self, client: HostClient, run_id: str) -> None:
        super().__init__()
        self.client = client
        self.run_id = run_id
        self._event_seq = 0
        self._revision = 0
        self._wait_kind: str | None = None
        self._active_node: str | None = None
        self._answer_inputs: dict[str, TextArea] = {}
        self._decision_options: list[str] = []
        self._poll_signature: tuple[Any, ...] | None = None
        self._events_error_notified = False
        self._last_markdown: str | None = None
        self._context_revision: int | None = None
        self._pending_action_panel: tuple[dict[str, Any], dict[str, Any] | None] | None = None
        self._history_scrolled_to_top = False
        self._show_technical_context = False
        self._last_steward_markdown: str | None = None
        self._last_technical_markdown: str | None = None
        self._flow: dict[str, Any] | None = None
        self._last_run_payload: dict[str, Any] | None = None
        self._focus_main_panel_on_ready = True

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="run-header-bar"):
            yield Static("", id="run-summary")
            yield Button("Show technical context", id="toggle-tech-context")
        with VerticalScroll(id="run-scroll"):
            yield Markdown("_Loading history…_", id="context-markdown")
            yield Vertical(id="action-panel")
            yield Markdown("", id="technical-markdown")
        yield Footer()

    DEFAULT_CSS = """
    #run-header-bar {
        height: auto;
        padding: 0 1;
    }
    #run-summary {
        width: 1fr;
    }
    #toggle-tech-context {
        width: auto;
        min-width: 22;
    }
    #run-scroll {
        height: 1fr;
        padding: 0 1;
        border: solid $primary-darken-2;
    }
    #context-markdown {
        width: 100%;
        height: auto;
        padding: 0 0 1 0;
    }
    #action-panel {
        width: 100%;
        height: auto;
        padding: 0 0 1 0;
    }
    #action-panel .wait-section-heading {
        width: 100%;
        height: auto;
        text-style: bold;
        margin-top: 1;
    }
    #action-panel .clarifying-question {
        width: 100%;
        height: auto;
        margin-top: 1;
    }
    #action-panel .clarifying-answer {
        width: 100%;
        height: 5;
        margin-bottom: 1;
    }
    #technical-markdown {
        width: 100%;
        height: auto;
        padding: 1 0 0 0;
        display: none;
    }
    #technical-markdown.-visible {
        display: block;
    }
    """

    def on_mount(self) -> None:
        workspace = getattr(self.client, "workspace", None)
        registry = getattr(self.client, "registry", None)
        if isinstance(workspace, Path):
            reg = registry if isinstance(registry, str) else None
            self._flow = load_operator_flow(workspace, registry=reg)
        self.action_refresh_all()
        self.set_interval(2.0, self._trigger_background_poll)
        self._focus_main_panel()

    def _focus_main_panel(self) -> None:
        scroll = self.query_one("#run-scroll", VerticalScroll)
        scroll.focus(scroll_visible=False)

    def _operator_flow(self) -> dict[str, Any] | None:
        return self._flow

    def _trigger_background_poll(self) -> None:
        self._background_poll()

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_refresh_all(self) -> None:
        self._background_full_refresh()

    @work(thread=True, exclusive=True)
    def _background_full_refresh(self) -> None:
        run_result = self.client.get_run(self.run_id)
        context_json = (
            self.client.run_context_json(self.run_id)
            if run_result.get("ok") and _needs_context_json_for_wait(run_result)
            else None
        )
        context_md = (
            self.client.run_operator_history_markdown(self.run_id)
            if run_result.get("ok")
            else None
        )
        technical_md = (
            self.client.run_context_markdown(self.run_id)
            if run_result.get("ok") and self._show_technical_context
            else None
        )
        events_result = self.client.run_events(
            self.run_id,
            after_seq=self._event_seq,
            block_ms=0,
        )
        self.app.call_from_thread(
            self._apply_full_refresh,
            run_result,
            context_json,
            context_md,
            technical_md,
            events_result,
        )

    @work(thread=True, exclusive=True)
    def _background_poll(self) -> None:
        events_result = self.client.run_events(
            self.run_id,
            after_seq=self._event_seq,
            block_ms=400,
        )
        run_result = self.client.get_run(self.run_id)
        context_json = None
        context_md = None
        technical_md = None
        if run_result.get("ok"):
            sig = _run_signature(run_result)
            run_revision = int(run_result.get("revision") or 0)
            needs_context = sig != self._poll_signature or (
                self._context_revision is not None and run_revision > self._context_revision
            )
            if needs_context:
                context_md = self.client.run_operator_history_markdown(self.run_id)
                if _needs_context_json_for_wait(run_result):
                    context_json = self.client.run_context_json(self.run_id)
                if self._show_technical_context:
                    technical_md = self.client.run_context_markdown(self.run_id)
        self.app.call_from_thread(
            self._apply_background_poll,
            events_result,
            run_result,
            context_json,
            context_md,
            technical_md,
        )

    def _apply_full_refresh(
        self,
        run_result: dict[str, Any],
        context_json: dict[str, Any] | None,
        context_md: dict[str, Any] | None,
        technical_md: dict[str, Any] | None,
        events_result: dict[str, Any],
    ) -> None:
        self._append_events(events_result)
        if not run_result.get("ok"):
            self.notify(RunListScreen._error_message(run_result), severity="error", timeout=8)
            return
        self._poll_signature = _run_signature(run_result)
        self._apply_run_state(run_result, context=_context_packet(context_json))
        self._apply_context_markdown(context_md)
        self._apply_technical_context(run_result, technical_md)

    def _apply_background_poll(
        self,
        events_result: dict[str, Any],
        run_result: dict[str, Any],
        context_json: dict[str, Any] | None,
        context_md: dict[str, Any] | None,
        technical_md: dict[str, Any] | None,
    ) -> None:
        self._append_events(events_result)
        if not run_result.get("ok"):
            return
        sig = _run_signature(run_result)
        if sig != self._poll_signature:
            self._poll_signature = sig
            self._apply_run_state(run_result, context=_context_packet(context_json))
        elif context_json is not None:
            self._apply_run_state(run_result, context=_context_packet(context_json))
        if context_md is not None:
            self._apply_context_markdown(context_md)
        if technical_md is not None:
            self._apply_technical_context(run_result, technical_md)
        elif self._show_technical_context and run_result.get("ok"):
            self._refresh_technical_metadata(run_result)

    def _apply_run_state(
        self,
        run_payload: dict[str, Any],
        *,
        context: dict[str, Any] | None,
    ) -> None:
        self._revision = int(run_payload.get("revision") or 0)
        self._wait_kind = run_payload.get("wait_kind")
        self._active_node = str(run_payload.get("active_node_id") or "")
        self._last_run_payload = run_payload
        self._update_summary(run_payload)
        self._rebuild_action_panel(run_payload, context=context)
        if self._show_technical_context:
            self._refresh_technical_metadata(run_payload)

    def _update_summary(self, result: dict[str, Any]) -> None:
        summary = self.query_one("#run-summary", Static)
        step = node_step_title(self._active_node, self._operator_flow())
        needs = needs_label(self._wait_kind)
        status = run_status_label(
            result.get("status") if isinstance(result.get("status"), str) else None
        )
        summary.update(
            f"{self.run_id}  ·  {step}  ·  Status: {status}  ·  Needs: {needs}"
        )

    def _technical_metadata_markdown(self, run_payload: dict[str, Any]) -> str:
        visit = run_payload.get("active_visit_id") or "—"
        phase = run_payload.get("phase") or "—"
        node = run_payload.get("active_node_id") or self._active_node or "—"
        revision = int(run_payload.get("revision") or self._revision or 0)
        return (
            "## Technical context\n\n"
            f"- **revision:** {revision}\n"
            f"- **visit id:** {visit}\n"
            f"- **phase:** {phase}\n"
            f"- **node id:** `{node}`\n"
        )

    def _combined_technical_markdown(
        self,
        run_payload: dict[str, Any],
        steward_markdown: str,
    ) -> str:
        body = steward_markdown.strip()
        combined = self._technical_metadata_markdown(run_payload)
        if body:
            combined = f"{combined}\n{body}"
        return combined

    def _set_technical_markdown_visible(self, visible: bool) -> None:
        widget = self.query_one("#technical-markdown", Markdown)
        widget.remove_class("-visible")
        if visible:
            widget.add_class("-visible")

    def _apply_technical_context(
        self,
        run_payload: dict[str, Any] | None,
        result: dict[str, Any] | None,
    ) -> None:
        if not self._show_technical_context:
            self._clear_technical_context()
            return
        if run_payload is None or not run_payload.get("ok"):
            run_payload = self._last_run_payload
        if run_payload is None:
            self._set_technical_markdown("_Loading technical context…_")
            return
        if result is None:
            self._refresh_technical_metadata(run_payload)
            return
        if not result.get("ok"):
            message = RunListScreen._error_message(result)
            markdown = (
                f"{self._technical_metadata_markdown(run_payload)}\n\n**Error:** {message}"
            )
            self._set_technical_markdown(markdown)
            return
        steward = result.get("markdown")
        steward_text = steward.strip() if isinstance(steward, str) else ""
        self._last_steward_markdown = steward_text or None
        markdown = self._combined_technical_markdown(run_payload, steward_text)
        self._set_technical_markdown(markdown)

    def _refresh_technical_metadata(self, run_payload: dict[str, Any]) -> None:
        if not self._show_technical_context:
            return
        steward = self._last_steward_markdown or ""
        self._set_technical_markdown(self._combined_technical_markdown(run_payload, steward))

    def _set_technical_markdown(self, markdown: str) -> None:
        if markdown == self._last_technical_markdown:
            return
        self._last_technical_markdown = markdown
        widget = self.query_one("#technical-markdown", Markdown)
        widget.update(markdown)
        self._set_technical_markdown_visible(bool(markdown.strip()))

    def _clear_technical_context(self) -> None:
        self._last_technical_markdown = None
        self._last_steward_markdown = None
        widget = self.query_one("#technical-markdown", Markdown)
        widget.update("")
        self._set_technical_markdown_visible(False)

    @on(Button.Pressed, "#toggle-tech-context")
    def _on_toggle_technical_context(self) -> None:
        self._show_technical_context = not self._show_technical_context
        button = self.query_one("#toggle-tech-context", Button)
        button.label = (
            "Hide technical context"
            if self._show_technical_context
            else "Show technical context"
        )
        if not self._show_technical_context:
            self._clear_technical_context()
            return
        self._fetch_technical_context()

    @work(thread=True, exclusive=True)
    def _fetch_technical_context(self) -> None:
        run_result = self.client.get_run(self.run_id)
        technical_md = (
            self.client.run_context_markdown(self.run_id)
            if run_result.get("ok")
            else None
        )
        self.app.call_from_thread(self._apply_technical_context, run_result, technical_md)

    def _rebuild_action_panel(
        self,
        run_payload: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        self._pending_action_panel = (run_payload, context)
        self._rebuild_action_panel_worker()

    @work(exclusive=True, group="action-panel")
    async def _rebuild_action_panel_worker(self) -> None:
        pending = self._pending_action_panel
        if pending is None:
            return
        run_payload, context = pending
        panel = self.query_one("#action-panel", Vertical)
        widgets = self._action_panel_widgets(run_payload, context=context)
        async with panel.batch():
            await panel.remove_children()
            if widgets:
                await panel.mount(*widgets)
        if self._focus_main_panel_on_ready:
            self._focus_main_panel_on_ready = False
            self._focus_main_panel()

    def _action_panel_widgets(
        self,
        run_payload: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> list[Button | Input | Markdown | Static | TextArea]:
        self._answer_inputs.clear()
        self._decision_options.clear()
        widgets: list[Button | Input | Markdown | Static | TextArea] = []

        if _parked_record(run_payload) is None:
            return widgets

        commands = _parked_commands(run_payload)
        wait_kind = run_payload.get("wait_kind")
        active_node = str(run_payload.get("active_node_id") or self._active_node or "")
        if active_node == EXECUTE_START_NODE and wait_kind == "decision":
            widgets.append(
                Static(
                    "Execute authorization — records start and advances into execute.intake "
                    "(same as `foundry start`)."
                )
            )
            widgets.append(Button("Authorize execute (start)", id="start-btn", variant="primary"))
            if _commands_include_advance(commands):
                widgets.append(Button("Advance", id="advance-btn", variant="default"))
            if _commands_include_retry(commands):
                widgets.append(Button("Retry", id="retry-btn", variant="default"))
            return widgets
        if wait_kind == "decision":
            options: list[str] = gate_options(context) if context else []
            if not options:
                options = ["accept", "reject"]
            self._decision_options = list(options)
            widgets.append(Static("Gate decision — choose an option:"))
            for index, option in enumerate(options):
                widgets.append(
                    Button(
                        option,
                        id=f"decide-opt-{index}",
                        variant="primary",
                    )
                )
            widgets.append(Static("Or type a custom option and press Decide:"))
            widgets.append(Input(placeholder="decision value", id="decide-custom"))
            widgets.append(Button("Decide (custom)", id="decide-custom-btn"))
        elif wait_kind == "user_input":
            questions: list[dict[str, Any]] = (
                open_clarifying_questions(context) if context else []
            )
            if not questions:
                widgets.append(
                    Static(
                        "user_input wait — no open questions in context; use Advance after fixing."
                    )
                )
            else:
                widgets.append(Static("Questions and answers", classes="wait-section-heading"))
                for item in questions:
                    qid = str(item.get("id") or "")
                    if not qid:
                        continue
                    question_md = format_clarifying_question_markdown(item)
                    if question_md:
                        widgets.append(Markdown(question_md, classes="clarifying-question"))
                    field = TextArea(id=f"answer-{qid}", classes="clarifying-answer")
                    self._answer_inputs[qid] = field
                    widgets.append(field)
                widgets.append(Button("Submit answers", id="submit-answers", variant="primary"))
        if _commands_include_advance(commands):
            widgets.append(Button("Advance", id="advance-btn", variant="default"))
        if _commands_include_retry(commands):
            widgets.append(Button("Retry", id="retry-btn", variant="default"))
        return widgets

    @on(Focus)
    def _scroll_wait_control_into_view(self, event: Focus) -> None:
        widget = event.widget
        if not isinstance(widget, (Input, Button, TextArea)):
            return
        control_id = str(widget.id or "")
        if not control_id.startswith(("answer-", "decide-", "submit-")) and control_id not in (
            "start-btn",
            "advance-btn",
            "retry-btn",
        ):
            return
        scroll = self.query_one("#run-scroll", VerticalScroll)
        scroll.scroll_to_widget(widget, animate=False)

    def _run_scroll(self) -> VerticalScroll:
        return self.query_one("#run-scroll", VerticalScroll)

    @on(Button.Pressed, "#advance-btn")
    def _advance_button(self) -> None:
        self.action_advance_run()

    @on(Button.Pressed, "#retry-btn")
    def _retry_button(self) -> None:
        self.action_retry_run()

    @on(Button.Pressed)
    def _on_decide_button(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("decide-opt-"):
            try:
                index = int(button_id.removeprefix("decide-opt-"))
            except ValueError:
                return
            if 0 <= index < len(self._decision_options):
                self._submit_decision(self._decision_options[index])
        elif button_id == "decide-custom-btn":
            custom = self.query_one("#decide-custom", Input)
            if custom.value.strip():
                self._submit_decision(custom.value.strip())
        elif button_id == "submit-answers":
            self._submit_answers()
        elif button_id == "start-btn":
            self.action_start_execute()

    def _submit_decision(self, decision: str) -> None:
        self._run_decide(decision)

    @work(thread=True)
    def _run_decide(self, decision: str) -> None:
        result = self.client.decide(
            self.run_id,
            decision=decision,
            expected_revision=self._revision,
        )
        self.app.call_from_thread(self._after_decide, result, decision)

    def _after_decide(self, result: dict[str, Any], decision: str) -> None:
        if not result.get("ok"):
            self.notify(RunListScreen._error_message(result), severity="error", timeout=8)
            return
        self.notify(f"Recorded decision {decision!r}", timeout=4)
        self._revision = int(result.get("revision") or self._revision)
        self.action_refresh_all()

    def _submit_answers(self) -> None:
        answers = {qid: field.text.strip() for qid, field in self._answer_inputs.items()}
        if not answers or any(not text for text in answers.values()):
            self.notify("All answer fields must be non-empty", severity="warning", timeout=5)
            return
        self._run_answer(answers)

    @work(thread=True)
    def _run_answer(self, answers: dict[str, str]) -> None:
        result = self.client.answer(
            self.run_id,
            answers=answers,
            expected_revision=self._revision,
        )
        self.app.call_from_thread(self._after_answer, result)

    def _after_answer(self, result: dict[str, Any]) -> None:
        if not result.get("ok"):
            self.notify(RunListScreen._error_message(result), severity="error", timeout=8)
            return
        self.notify("Answers submitted", timeout=4)
        self._revision = int(result.get("revision") or self._revision)
        self.action_refresh_all()

    def action_advance_run(self) -> None:
        self._run_advance()

    def action_retry_run(self) -> None:
        self._run_retry()

    @work(thread=True)
    def _run_retry(self) -> None:
        result = self.client.retry(
            self.run_id,
            expected_revision=self._revision,
        )
        self.app.call_from_thread(self._after_retry, result)

    def _after_retry(self, result: dict[str, Any]) -> None:
        if not result.get("ok"):
            self.notify(RunListScreen._error_message(result), severity="error", timeout=10)
            return
        self._revision = int(result.get("revision") or self._revision)
        self.notify("Retry complete", timeout=3)
        self.action_refresh_all()

    @work(thread=True)
    def _run_advance(self) -> None:
        result = self.client.advance(
            self.run_id,
            expected_revision=self._revision,
        )
        self.app.call_from_thread(self._after_advance, result)

    def _after_advance(self, result: dict[str, Any]) -> None:
        if not result.get("ok"):
            self.notify(RunListScreen._error_message(result), severity="error", timeout=10)
            return
        self._revision = int(result.get("revision") or self._revision)
        self.notify("Advance complete", timeout=3)
        self.action_refresh_all()

    def action_start_execute(self) -> None:
        self._run_start()

    @work(thread=True)
    def _run_start(self) -> None:
        start_result = self.client.start_execute(
            self.run_id,
            expected_revision=self._revision,
        )
        if not start_result.get("ok"):
            self.app.call_from_thread(self._notify_error, start_result)
            return
        revision = int(start_result.get("revision") or self._revision)
        advance_result = self.client.advance(
            self.run_id,
            expected_revision=revision,
        )
        self.app.call_from_thread(self._after_start, start_result, advance_result)

    def _notify_error(self, result: dict[str, Any]) -> None:
        self.notify(RunListScreen._error_message(result), severity="error", timeout=10)

    def _after_start(self, start_result: dict[str, Any], advance_result: dict[str, Any]) -> None:
        if not advance_result.get("ok"):
            self.notify(RunListScreen._error_message(advance_result), severity="error", timeout=10)
            return
        self._revision = int(advance_result.get("revision") or start_result.get("revision") or 0)
        self.notify("Execute authorized and advanced", timeout=4)
        self.action_refresh_all()

    def _apply_context_markdown(self, result: dict[str, Any] | None) -> None:
        widget = self.query_one("#context-markdown", Markdown)
        if result is None:
            self._set_history_markdown(widget, "_Context unavailable._")
            return
        if not result.get("ok"):
            self._set_history_markdown(widget, f"**Error:** {RunListScreen._error_message(result)}")
            return
        revision = result.get("revision")
        if isinstance(revision, int):
            self._context_revision = revision
        markdown = result.get("markdown")
        if isinstance(markdown, str) and markdown.strip():
            self._set_history_markdown(widget, markdown)
        else:
            self._set_history_markdown(widget, "_No history yet for this run._")

    def _set_history_markdown(self, widget: Markdown, markdown: str) -> None:
        if markdown == self._last_markdown:
            return
        scroll = self._run_scroll()
        saved_y = scroll.scroll_y
        self._last_markdown = markdown
        widget.update(markdown)
        if not self._history_scrolled_to_top:
            self._history_scrolled_to_top = True
            scroll.scroll_home()
        else:
            scroll.scroll_to(y=saved_y, animate=False)

    def _append_events(self, result: dict[str, Any]) -> None:
        if not result.get("ok"):
            if not self._events_error_notified:
                self.notify(
                    RunListScreen._error_message(result),
                    severity="warning",
                    timeout=6,
                )
                self._events_error_notified = True
            return
        self._events_error_notified = False
        for event in result.get("events") or []:
            if not isinstance(event, dict):
                continue
            seq = event.get("seq")
            if isinstance(seq, int):
                self._event_seq = max(self._event_seq, seq)
            if isinstance(event.get("revision"), int):
                rev = int(event["revision"])
                if self._context_revision is None or rev > self._context_revision:
                    self._context_revision = rev


class FoundryTuiApp(App[None]):
    """Root Textual application (interactive attach)."""

    TITLE = "Foundry attach"
    SUB_TITLE = "Job host client"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        client: HostClient,
        *,
        initial_run_id: str | None = None,
    ) -> None:
        super().__init__()
        self._client = client
        self._initial_run_id = initial_run_id

    def on_mount(self) -> None:
        if not self._client.running():
            self.push_screen(HostPromptScreen(), self._on_host_prompt)
        else:
            self._open_initial_screen()

    def _on_host_prompt(self, start: bool | None) -> None:
        if not start:
            self.exit()
            return
        self._start_host_async()

    @work(thread=True)
    def _start_host_async(self) -> None:
        result = self._client.start_host()
        self.call_from_thread(self._after_host_start, result)

    def _after_host_start(self, result: dict[str, Any]) -> None:
        if not result.get("ok"):
            err = result.get("error") if isinstance(result.get("error"), dict) else {}
            self.notify(
                f"[{err.get('code')}] {err.get('message')}",
                severity="error",
                timeout=10,
            )
            self.exit()
            return
        self.notify("Host started", timeout=3)
        self._open_initial_screen()

    def _open_initial_screen(self) -> None:
        if self._initial_run_id:
            self.push_screen(RunDetailScreen(self._client, self._initial_run_id))
        else:
            self.push_screen(RunListScreen(self._client))


def run_tui(
    *,
    workspace: Path,
    registry: str | None = None,
    run_id: str | None = None,
) -> None:
    client = HostClient(workspace, registry=registry)
    app = FoundryTuiApp(client, initial_run_id=run_id)
    app.run()
