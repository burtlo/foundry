# Foundry Textual TUI

**Doc kind:** feature-record

## Summary

**`foundry attach`** is the operator Textual client ([Textual](https://textual.textualize.io/)). It lists runs with human column labels, shows operator history and human wait actions in one scroll, and submits `run.decide`, `run.answer`, `run.start`, and `run.advance` over the job host socket — no subprocess `foundry run context` and no embedded engine logic.

**`foundry tui`** is a deprecated alias that prints a notice and runs the same UI.

## Dependencies

- `textual` (see `.cursor/foundry/cli/requirements.txt`)
- Running job host (`foundry host start`); attach can prompt to start the host when it is down

## Host RPCs used

| UI area | Method |
|---------|--------|
| Run list | `run.list` |
| Status / revision / wait | `run.get` |
| Operator history pane | `run.operator_history` (`format=markdown`) |
| Technical context (toggle) | `run.context` (`format=markdown`) |
| Revision / refresh signal | `run.events` (`after_seq`, `block_ms`) — not rendered as an event log |
| Gate decide | `run.decide` |
| Clarifying answers | `run.answer` |
| Execute authorization | `run.start` then `run.advance` |
| Progress | `run.advance` |

Long `run.advance` uses the same client timeout policy as the CLI ([run-advance.md](../cli/run-advance.md)).

Host RPCs run on worker threads. The run detail view polls every ~2s (`run.events` long-poll + `run.get`) and refreshes the header, operator history, wait panel, and (when enabled) technical context when revision or wait state changes (e.g. host auto-advance).

## Code map

| Module | Role |
|--------|------|
| `foundry_cli/user_cli.py` | `cmd_attach` CLI entry |
| `foundry_cli/tui/app.py` | Textual screens, help panel, bindings |
| `foundry_cli/tui/host_client.py` | `call_host` wrapper |
| `foundry_cli/operator_history.py` | Operator history projection |
| `foundry_cli/run_labels.py` | Needs labels and node step titles |

## Operator doc

[Interactive attach](../operator-runbook.md#interactive-attach) and [TUI mode](../operator-runbook.md#tui-mode-textual) in the operator runbook.

## Tests

- `tests/unit/test_tui.py` — headless list, run view, wait panel, help chord, layout probes
- `tests/unit/test_operator_history.py` — projection and host handler
