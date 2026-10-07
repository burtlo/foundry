"""Foundry Textual TUI — host-only operator client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, RichLog, Static

from foundry_cli.tui.host_client import HostClient, gate_options, open_clarifying_questions

EXECUTE_START_NODE = "execute.start"


def _run_signature(run_payload: dict[str, Any]) -> tuple[Any, ...]:
    return (
        run_payload.get("revision"),
        run_payload.get("wait_kind"),
        run_payload.get("active_node_id"),
        run_payload.get("status"),
        run_payload.get("phase"),
    )


def _context_packet(context_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not context_result or not context_result.get("ok"):
        return None
    packet = context_result.get("context")
    return packet if isinstance(packet, dict) else None


def _needs_context_json_for_wait(run_payload: dict[str, Any]) -> bool:
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


class RunListScreen(Screen):
    """Workspace run list via ``run.list``."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("r", "refresh_runs", "Refresh"),
        Binding("enter", "open_run", "Open"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self, client: HostClient) -> None:
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Runs — select a row and press Enter", id="run-list-title")
        yield DataTable(id="run-table", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#run-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("run_id", "status", "node", "wait", "revision")
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
        for row in result.get("runs") or []:
            if not isinstance(row, dict):
                continue
            table.add_row(
                str(row.get("run_id") or ""),
                str(row.get("status") or ""),
                str(row.get("active_node_id") or ""),
                str(row.get("wait_kind") or ""),
                str(row.get("revision") or ""),
            )

    def action_open_run(self) -> None:
        table = self.query_one("#run-table", DataTable)
        if table.row_count == 0:
            return
        row_key = table.cursor_row
        if row_key is None:
            return
        run_id = str(table.get_row_at(row_key)[0])
        self.app.push_screen(RunDetailScreen(self.client, run_id))

    @staticmethod
    def _error_message(result: dict[str, Any]) -> str:
        err = result.get("error") if isinstance(result.get("error"), dict) else {}
        code = err.get("code") or "ERROR"
        message = err.get("message") or "Request failed"
        return f"[{code}] {message}"


class RunDetailScreen(Screen):
    """Run status, wait actions, events, and steward context."""

    BINDINGS: ClassVar[list[Binding]] = [
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
        self._answer_inputs: dict[str, Input] = {}
        self._decision_options: list[str] = []
        self._poll_signature: tuple[Any, ...] | None = None
        self._events_error_notified = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="run-summary")
        with Horizontal(id="main-panels"):
            with Vertical(id="left-panel"):
                yield Static("Wait / actions", classes="panel-title")
                yield VerticalScroll(id="wait-panel")
                yield Static("Events", classes="panel-title")
                yield RichLog(id="event-log", wrap=True, highlight=True, markup=False)
            with Vertical(id="right-panel"):
                yield Static("Steward context (markdown)", classes="panel-title")
                yield RichLog(id="context-log", wrap=True, highlight=False, markup=False)
        yield Footer()

    DEFAULT_CSS = """
    #main-panels {
        height: 1fr;
    }
    #left-panel {
        width: 45%;
        height: 1fr;
        border-right: solid $primary;
    }
    #right-panel {
        width: 55%;
        height: 1fr;
    }
    .panel-title {
        padding: 0 1;
        background: $boost;
        color: $text;
    }
    #event-log, #context-log {
        height: 1fr;
        border: solid $primary-darken-2;
    }
    #wait-panel {
        height: auto;
        max-height: 14;
        padding: 0 1;
    }
    """

    def on_mount(self) -> None:
        self.action_refresh_all()
        self.set_interval(2.0, self._trigger_background_poll)

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
            self.client.run_context_markdown(self.run_id) if run_result.get("ok") else None
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
        if run_result.get("ok"):
            sig = _run_signature(run_result)
            if sig != self._poll_signature:
                context_md = self.client.run_context_markdown(self.run_id)
                if _needs_context_json_for_wait(run_result):
                    context_json = self.client.run_context_json(self.run_id)
        self.app.call_from_thread(
            self._apply_background_poll,
            events_result,
            run_result,
            context_json,
            context_md,
        )

    def _apply_full_refresh(
        self,
        run_result: dict[str, Any],
        context_json: dict[str, Any] | None,
        context_md: dict[str, Any] | None,
        events_result: dict[str, Any],
    ) -> None:
        self._append_events(events_result)
        if not run_result.get("ok"):
            self.notify(RunListScreen._error_message(run_result), severity="error", timeout=8)
            return
        self._poll_signature = _run_signature(run_result)
        self._apply_run_state(run_result, context=_context_packet(context_json))
        self._apply_context_markdown(context_md)

    def _apply_background_poll(
        self,
        events_result: dict[str, Any],
        run_result: dict[str, Any],
        context_json: dict[str, Any] | None,
        context_md: dict[str, Any] | None,
    ) -> None:
        self._append_events(events_result)
        if not run_result.get("ok"):
            return
        sig = _run_signature(run_result)
        if sig == self._poll_signature:
            return
        self._poll_signature = sig
        self._apply_run_state(run_result, context=_context_packet(context_json))
        if context_md is not None:
            self._apply_context_markdown(context_md)

    def _apply_run_state(
        self,
        run_payload: dict[str, Any],
        *,
        context: dict[str, Any] | None,
    ) -> None:
        self._revision = int(run_payload.get("revision") or 0)
        self._wait_kind = run_payload.get("wait_kind")
        self._active_node = str(run_payload.get("active_node_id") or "")
        self._update_summary(run_payload)
        self._rebuild_wait_panel(run_payload, context=context)

    def _update_summary(self, result: dict[str, Any]) -> None:
        wait = result.get("wait") if isinstance(result.get("wait"), dict) else {}
        summary = self.query_one("#run-summary", Static)
        summary.update(
            f"run={self.run_id}  phase={result.get('phase')}  status={result.get('status')}  "
            f"node={self._active_node}  revision={self._revision}  "
            f"wait={self._wait_kind or '—'}  {wait.get('summary') or ''}"
        )

    def _rebuild_wait_panel(
        self,
        run_payload: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        panel = self.query_one("#wait-panel", VerticalScroll)
        panel.remove_children()
        self._answer_inputs.clear()
        self._decision_options.clear()

        wait_kind = run_payload.get("wait_kind")
        active_node = str(run_payload.get("active_node_id") or self._active_node or "")
        if active_node == EXECUTE_START_NODE and wait_kind == "decision":
            panel.mount(
                Static(
                    "Execute authorization — records start and advances into execute.intake "
                    "(same as `foundry start`)."
                )
            )
            panel.mount(Button("Authorize execute (start)", id="start-btn", variant="primary"))
            return
        if wait_kind == "decision":
            options: list[str] = gate_options(context) if context else []
            if not options:
                options = ["accept", "reject"]
            self._decision_options = list(options)
            panel.mount(Static("Gate decision — choose an option:"))
            for index, option in enumerate(options):
                panel.mount(
                    Button(
                        option,
                        id=f"decide-opt-{index}",
                        variant="primary",
                    )
                )
            panel.mount(Static("Or type a custom option and press Decide:"))
            custom = Input(placeholder="decision value", id="decide-custom")
            panel.mount(custom)
            panel.mount(Button("Decide (custom)", id="decide-custom-btn"))
        elif wait_kind == "user_input":
            questions: list[dict[str, Any]] = (
                open_clarifying_questions(context) if context else []
            )
            if not questions:
                panel.mount(
                    Static(
                        "user_input wait — no open questions in context; use Advance after fixing."
                    )
                )
            else:
                panel.mount(Static("Clarifying answers:"))
                for item in questions:
                    qid = str(item.get("id") or "")
                    text = str(item.get("text") or qid)
                    panel.mount(Label(f"{qid}: {text}"))
                    field = Input(placeholder=f"Answer for {qid}", id=f"answer-{qid}")
                    self._answer_inputs[qid] = field
                    panel.mount(field)
                panel.mount(Button("Submit answers", id="submit-answers", variant="primary"))
        elif wait_kind == "agent":
            panel.mount(
                Static(
                    "Agent judgment wait — use Advance (requires bridge on host) "
                    "or enable host auto-advance."
                )
            )
            panel.mount(Button("Advance", id="advance-btn", variant="primary"))
        else:
            panel.mount(Static("No human wait — Advance to progress the run."))
            panel.mount(Button("Advance", id="advance-btn", variant="primary"))

    @on(Button.Pressed, "#advance-btn")
    def _advance_button(self) -> None:
        self.action_advance_run()

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
        answers = {qid: field.value.strip() for qid, field in self._answer_inputs.items()}
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
        log = self.query_one("#context-log", RichLog)
        log.clear()
        if result is None:
            log.write("(context unavailable)")
            return
        if not result.get("ok"):
            log.write(RunListScreen._error_message(result))
            return
        markdown = result.get("markdown")
        if isinstance(markdown, str) and markdown.strip():
            log.write(markdown)
        else:
            log.write("(empty context)")

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
            line = json.dumps(event, sort_keys=True)
            self.query_one("#event-log", RichLog).write(line)


class FoundryTuiApp(App[None]):
    """Root Textual application."""

    TITLE = "Foundry TUI"
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
