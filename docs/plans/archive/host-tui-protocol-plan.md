# Host TUI protocol (Phase 4)

Status: **shipped**

**Program:** [operator-integration-program.md](../operator-integration-program.md)  
**Feature record:** [host-tui-protocol.md](../../features/host-tui-protocol.md)

## Scope

- `run.context` on job host (json | markdown), delegating to existing context assembly.
- Optional `run.get` enrichment (`phase`, `wait_kind`, `status_reason`).
- Optional `run.events` long-poll (`block_ms`).
- Protocol tests; update [job-host-architecture.md](../concepts/job-host-architecture.md) command table.

## Exit criteria

A TUI client can load run context and status without subprocess `foundry run context`.
