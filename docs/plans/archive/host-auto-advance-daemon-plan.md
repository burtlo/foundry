# Host auto-advance daemon (Phase 3)

Status: **shipped**

**Program:** [operator-integration-program.md](../operator-integration-program.md)  
**Feature record:** [host-auto-advance.md](../../features/host-auto-advance.md)

## Problem

`recover_nonterminal_runs` runs one `advance_run_durable` per run at host startup only; agent waits stall without manual `run advance`.

## Scope

- `AutoAdvanceLoop` in host process (optional `foundry host start --auto-advance`).
- Advance when `wait` is null or `wait.kind == agent`; never auto `decide` / `answer`.
- Backoff, per-run locking, adapter from host env.
- Tests with stub adapter; runbook “hands-off shape” prerequisites.

## Exit criteria

Stub adapter: daemon advances a parked run at `agent` wait without manual `run advance`.
