# Phase 5 — User CLI for Shape

Status: **complete**

Related: [job-host architecture](../docs/concepts/job-host-architecture.md), [Phase 3](03-job-host.md), [Phase 4](04-agent-connection.md), [delivery index](README.md).

## Design

### User commands

| Command | Role |
|---------|------|
| `foundry shape --input` / `--input-file` | Persist verbatim request on run config, create run, advance to first wait via host when running |
| `foundry runs` | List runs with status, active node, wait kind (host `run.list` when host is up) |
| `foundry status [RUN]` | Snapshot summary; default run when exactly one active run |
| `foundry attach RUN` | Snapshot + ledger events (`--json` or `--no-follow` for one shot; else stream until Ctrl-C) |
| `foundry decide RUN <option>` | User gate decision when `wait.kind=decision`; typed errors otherwise |
| `foundry start` | Implemented in Phase 6 — see [06-execute-verify](06-execute-verify.md) |
| `foundry host …` | Unchanged local service control (Phase 3) |

Low-level `run`, `visit`, `gate`, `ledger` commands remain for compatibility and tests.

### Host protocol extensions

| Method | Notes |
|--------|--------|
| `run.create` | `work_prompt`, optional `flow_id` / `run_id`, `idempotency_key` |
| `run.decide` | `decision`, `expected_revision`, `idempotency_key` |

Existing `run.advance`, `run.get`, `run.list`, `run.events` are reused from the user path.

### Persistence and errors

- `shape` verifies `config.shape.work_prompt` on disk **before** returning after advance.
- `--json` responses use the standard `{ok, …}` / `{ok: false, error: {code, message}}` envelope.
- **`STALE_REVISION`** on conflicting `--revision` (same as Phase 2).
- **`WAIT_KIND_MISMATCH`** when `foundry decide` is used while the active wait is not `decision`.

### Auto-host

Unless `--no-host`, `foundry shape` starts the background job host when it is not already running, then uses host mutations for create/advance.

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| `foundry shape` creates run, persists work_prompt, advances to first wait | Met — unit test |
| User list/status/attach/decide commands wired to host when running | Met |
| Host `run.create` / `run.decide` | Met |
| Typed `WAIT_KIND_MISMATCH`, `STALE_REVISION` | Met |
| `foundry start` gated stub | Met |
| Phase doc + tests | Met |

## Verification

From `.cursor/foundry/cli`:

```text
python -m pytest tests/unit/test_shape_cli.py tests/unit/test_host_protocol.py -q
```

## Out of scope (Phase 6)

- Full `foundry start` / `retry` / `cancel` Execute UX
- TUI / web UI
