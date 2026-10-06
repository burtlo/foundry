# Phase 6 — Execute and Verify (user CLI)

Status: **complete**

Related: [job-host architecture](../job-host-architecture.md), [Phase 5](05-shape-cli.md), [delivery plan](../job-host-delivery.md).

## Design

### User commands

| Command | Role |
|---------|------|
| `foundry start [RUN]` | Explicit Shape → Execute authorization at `execute.start`; records `execute.authorization.recorded`, accepts gate, advances via host |
| `foundry retry RUN` | Resume halted / `execution_error` / operator-wait runs; optional `--reason`; advances one step |
| `foundry cancel RUN --reason` | Halt a non-terminal run with ledgered operator cancel reason |
| `foundry status` / `attach` / `decide` | Unchanged supervision for execute and verify gates |

`start` is valid only when the active node is `execute.start`, the wait is `decision`, and `shape.record` has sealed. Generic `foundry decide` remains available for other user gates.

### Host protocol extensions

| Method | Notes |
|--------|--------|
| `run.start` | `expected_revision`, `idempotency_key` |
| `run.retry` | optional `reason` |
| `run.cancel` | required `reason` |

### Ledger

- `execute.authorization.recorded` — explicit developer authorization before execute intake
- `operator.action` — `retry` or `cancel` with reason metadata

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| `foundry start` at `execute.start` records authorization and reaches `execute.intake` boundary | Met — unit test |
| `foundry retry` / `cancel` with typed errors and reasons | Met — unit tests |
| Host `run.start` / `run.retry` / `run.cancel` | Met |
| Supervision via existing status/attach/decide | Met — reused Phase 5 commands |
| Phase doc + tests | Met |

## Verification

From `.cursor/foundry/cli`:

```text
python -m pytest tests/unit/test_execute_cli.py tests/unit/test_shape_cli.py tests/unit/test_host_protocol.py -q
python -m pytest tests/acceptance -q --ignore=tests/acceptance/test_dev_commands.py
```

## Out of scope

- TUI / web UI / distributed queue
- Full verify-phase automation beyond existing engine boundaries
