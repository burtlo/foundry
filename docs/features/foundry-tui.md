# Foundry Textual TUI

**Doc kind:** feature-record

## Summary

`foundry tui` is a **host-only** [Textual](https://textual.textualize.io/) client for operators. It lists runs, shows steward context and ledger events, and submits `run.decide`, `run.answer`, `run.start`, and `run.advance` over the job host socket — no subprocess `foundry run context` and no embedded engine logic.

## Dependencies

- `textual` (see `.cursor/foundry/cli/requirements.txt`)
- Running job host (`foundry host start`); the TUI can prompt to start the host when it is down

## Host RPCs used

| UI area | Method |
|---------|--------|
| Run list | `run.list` |
| Status / revision / wait | `run.get` |
| Context pane | `run.context` (`format=markdown`) |
| Event log | `run.events` (`after_seq`, `block_ms`) |
| Gate decide | `run.decide` |
| Clarifying answers | `run.answer` |
| Execute authorization | `run.start` then `run.advance` |
| Progress | `run.advance` |

Long `run.advance` uses the same client timeout policy as the CLI ([run-advance.md](../cli/run-advance.md)).

Host RPCs run on worker threads; the run detail view polls every 2s (`run.events` long-poll + `run.get`) and refreshes the summary, wait panel, and context when revision or wait state changes (e.g. host auto-advance).

## Code map

| Module | Role |
|--------|------|
| `foundry_cli/tui_commands.py` | `cmd_tui` CLI entry |
| `foundry_cli/tui/app.py` | Textual screens and bindings |
| `foundry_cli/tui/host_client.py` | `call_host` wrapper |

## Operator doc

[TUI mode](../operator-runbook.md#tui-mode-textual) in the operator runbook.

## Tests

- `tests/unit/test_tui.py` — context helpers, mocked `call_host`, headless Textual pilot smoke
