# Feature records (shipped behavior)

Authoritative **as-built** descriptions of the Foundry CLI and implementation flow runtime. Implement and debug from these; use [docs/plans/](../plans/README.md) only for incomplete work.

| Record | Scope |
|--------|--------|
| [implementation-flow-runtime.md](implementation-flow-runtime.md) | Implementation flow: advance, mechanisms, gates, expressions, test map |
| [judgment-bridge.md](judgment-bridge.md) | In-repo HTTP bridge + Cursor SDK for judgment tasks |
| [host-auto-advance.md](host-auto-advance.md) | Optional host background auto-advance loop |
| [host-tui-protocol.md](host-tui-protocol.md) | Host RPC for TUI: `run.context`, enriched status, event long-poll |
| [foundry-tui.md](foundry-tui.md) | Textual `foundry tui` host client |
| [Operator runbook](../operator-runbook.md) | Application-workspace CLI scenarios: host, shape, waits, execute start (operator guide; not a feature record) |

Conceptual background: [docs/concepts/](../concepts/README.md). Generated inventory: [docs/generated/](../generated/README.md).
