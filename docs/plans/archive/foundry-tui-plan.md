# Foundry Textual TUI (Phase 5)

Status: **shipped**

**Program:** [operator-integration-program.md](../operator-integration-program.md)  
**Feature record:** [foundry-tui.md](../../features/foundry-tui.md)

**Depends on:** Phase 3 (auto-advance), Phase 4 (host protocol). Host client timeouts (phase 1) are shipped — see [run-advance.md](../cli/run-advance.md).

## Scope

- `foundry tui` (optional `--run`) using Textual.
- Run list, detail, wait panel, actions (`decide`, `answer`, `start`, `run.advance`), events, context markdown.
- Host-only client; prompt `host start` if unavailable.
- Runbook “TUI mode” section when shipped.

## Exit criteria

Operator resolves a user gate and a `user_input` wait from the TUI without raw `gate decide` / visit commands.
