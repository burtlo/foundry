# Phase 3 — Persistent local job host

Status: **complete**

Related: [job-host architecture](../docs/concepts/job-host-architecture.md), [Phase 2](02-run-engine.md), [delivery index](README.md).

## Design

### Process model

- One **local host per workspace** (v1). Discovery under `.foundry/host/`:
  - `state.json` — `pid`, `transport`, `address`, `protocol_version`, `started_at`
  - `host.lock` — exclusive lock during host startup
  - `socket` — Unix domain socket (non-Windows); Windows uses loopback TCP with port in `state.json`
- Foreground: `foundry host run` (tests). Background: `foundry host start` (detached subprocess running `python -m foundry_cli.host`).

### Control protocol (version 1)

Newline-delimited JSON request/response over the local socket.

| Method | Kind | Notes |
|--------|------|--------|
| `health` | read | Registry validation status |
| `run.get` | read | Snapshot summary |
| `run.list` | read | All runs under `.foundry/runs/` |
| `run.events` | read | `after_seq` → ledger tail |
| `run.advance` | mutate | Requires `expected_revision` + `idempotency_key`; delegates to Phase 2 engine |
| `host.stop` | mutate | Requires `idempotency_key`; shuts down server |

Mutations are idempotent per `idempotency_key` for the lifetime of the host process. Conflicting revisions return `STALE_REVISION` with current `revision` (same as CLI).

### CLI client mode

- `foundry host status|start|stop|run`
- `foundry run get|list|events|advance` — when the host is running, these call the control protocol unless `--local` is set (direct disk / in-process engine).

### Startup

On bind, the host validates workspace Foundry config and runs **recovery**: one bounded `advance` per non-terminal run (same path as `run recover`).

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| Run outlives short-lived CLI; inspectable via second invocation | Met — integration test |
| Local host + discovery under `.foundry/host/` | Met |
| Versioned JSON protocol (`health`, `run.get`, `run.list`, `run.advance`, `run.events`, `host.stop`) | Met |
| Mutations require `expected_revision` + idempotency key | Met — `run.advance` |
| Reuses Phase 2 advance/recover (no duplicated engine) | Met — `run_service.advance_run_durable` |
| Unit tests for protocol handlers | Met |
| Integration: host subprocess + `run create` + `run get` from second CLI | Met |

## Verification

From `.cursor/foundry/cli`:

```text
python -m pytest tests/unit/test_host_protocol.py tests/unit/test_host_integration.py -q
```

## Out of scope (later phases)

- Model adapter (Phase 4)
- User `foundry shape` / attach UX (Phase 5)
- Execute/verify (Phase 6)
- Distributed or multi-host
