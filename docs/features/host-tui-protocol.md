# Host TUI protocol

**Doc kind:** feature-record  
**Program:** [operator-integration-program.md](../plans/operator-integration-program.md) Phase 4

## Summary

The job host exposes read RPCs so a TUI (or other client) can load run status and steward context without subprocess `foundry run context`. `foundry run context`, `run get`, and `run events` route through the host when it is running (unless `--local`).

## Methods

### `run.context`

| Param | Role |
|-------|------|
| `run_id` / `run_dir` | Run selector (same as other run RPCs) |
| `visit` | Optional visit id (default active visit) |
| `flow_id` / `flow` | Optional flow override |
| `format` | `json` (default) or `markdown` |

**`json`:** `context` object (validated context-packet schema).  
**`markdown`:** `markdown` string plus `context` for clients that need both.

### `run.get` enrichments

In addition to existing fields: `phase` (`shape` \| `execute` \| `verify` \| `deliver` \| …), `wait_kind`, `status_reason`.

### `run.events` long-poll

| Param | Role |
|-------|------|
| `after_seq` | Return events with `seq > after_seq` |
| `block_ms` | Wait up to N ms for new events (cap 120s); `timed_out: true` when empty |

CLI: `foundry run events --block-ms 500`.

## Code map

| Module | Role |
|--------|------|
| `foundry_cli/run_context_service.py` | Shared context assembly |
| `foundry_cli/run_labels.py` | `phase_label` |
| `foundry_cli/host/handlers.py` | `run.context` dispatch |
| `foundry_cli/run_service.py` | `get_run` / `run_events` enrichments |

## Tests

- Unit: `tests/unit/test_host_tui_protocol.py`, `tests/unit/test_host_client_timeout.py` (`run.events` socket timeout)
- Acceptance: `tests/acceptance/features/job_host.feature` (host-routed `run context` markdown and `run events --block-ms`)

**Delivery plan (archived):** [host-tui-protocol-plan.md](../plans/archive/host-tui-protocol-plan.md).
