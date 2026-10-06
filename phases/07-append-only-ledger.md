# P7 — Append-only ledger

Status: **complete**

Related: [job-host architecture](../docs/concepts/job-host-architecture.md) (Persistence), [delivery index](README.md), [Phase 3](03-job-host.md).

## Design

### Per-run ledger file

- Path: `{run_dir}/ledger.jsonl` — one JSON event object per line.
- Appends use `fsync` after each commit batch (`ledger_store.append_events`).
- `snapshot.json` keeps an inline `ledger[]` for existing `ledger.py` callers; `storage_version: 2` marks migrated runs.

### Transaction order (`commit_snapshot`)

Under `run_lock`:

1. Optimistic revision check against on-disk snapshot.
2. Append **new** events (seq greater than committed tail) to `ledger.jsonl`.
3. Sync inline `ledger` from the file.
4. Atomically replace `snapshot.json`.

Events are durable before the snapshot pointer moves forward, so a crash after append but before snapshot replace can rebuild the inline ledger from `ledger.jsonl` on load.

### Migration

`migrate_run_storage(run_dir, snapshot)` on load:

- Inline-only runs: write `ledger.jsonl` once from `snapshot.ledger`, set `storage_version: 2`.
- Idempotent when the file already exists.

### Recovery (minimum)

- Corrupt or missing `snapshot.json` with a present `ledger.jsonl`: rebuild ledger inline via `repair_snapshot_from_ledger`, then rewrite snapshot.
- Truncated snapshot with a longer ledger file: on load, sync inline ledger from file and persist.

Full materialized-state replay from events is **out of scope**; only ledger seq and revision consistency are proven in tests.

### Host idempotency

- Path: `.foundry/host/idempotency.json`
- Survives host restart; TTL 24h; capped at 1000 keys.
- Applies to all host mutation methods that require `idempotency_key`.

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| `ledger.jsonl` append with fsync before snapshot replace | Met |
| Inline `ledger` remains for `ledger.py` | Met |
| Explicit migration + `storage_version: 2` | Met |
| Recovery from ledger when snapshot corrupt / behind file | Met |
| Durable host idempotency keys | Met |
| Existing acceptance suite unchanged | Met — verify below |

## Verification

From `.cursor/foundry/cli`:

```text
python -m pytest tests/unit/test_ledger_store.py tests/unit/test_run_store_durable.py tests/unit/test_host_protocol.py -q
python -m pytest tests/acceptance -q --ignore=tests/acceptance/dev_commands
```
