# Phase 2 — Durable advancement and recovery

Status: **complete**

Related: [job-host architecture](../docs/concepts/job-host-architecture.md), [Phase 1](01-shape-extraction.md), [delivery index](README.md).

## Implemented

### `run advance` / `run recover`

- **`foundry_cli/engine/advance.py`**: bounded advance loop with default step budget 8; stops at terminal run status, declared `run.wait`, or automatic work limit.
- **`run advance`**: loads snapshot under per-run file lock (`.run.lock`), optional `--revision` optimistic check, persists `wait` and ledger changes atomically.
- **`run recover`**: same engine path without revision precondition; marks response `recovered: true` for crash-resume proofs.
- **Shape intake integration**: when `config.shape.work_prompt` (or legacy `config.work_prompt` / `state.work_prompt`) is set on an opened `shape.intake` visit, advance invokes Phase 1 `run_shape_intake_complete` then continues until examine boundary.

### `run.revision` and `STALE_REVISION`

- Snapshot field **`revision`** (integer, starts at `1` on `run create`).
- Mutating CLI commands accept optional **`--revision`**; `commit_snapshot` compares to on-disk revision under lock and returns **`STALE_REVISION`** on conflict.
- Successful commits bump revision from the locked on-disk value (safe when in-memory copy is stale).

### `run.wait`

- Orthogonal nullable field on snapshot: `{id, visit_id, kind, created_at, request_ref, summary}`.
- Set when advancement stops for **`operator`** (missing work prompt / blocked intake), **`decision`** (user gate without decision), or **`agent`** (judgment steps including `shape.examine`).
- Cleared on successful gate decide / intake complete / transition when steward commands complete.

### Durability

- **`save_snapshot`**: write `snapshot.json.tmp`, fsync, atomic `os.replace`.
- Ledger remains inline; events appended in memory commit with the snapshot replace inside `run_lock`.

### CLI ergonomics

- **`run create --work-prompt`**: stores verbatim request on `config.shape` for engine advance.

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| Fresh process can resume via `run recover` / `run advance` at a declared boundary | Met — subprocess test |
| Exclusive per-run lock during advance | Met — `.run.lock` |
| Bounded advance until wait / halt / complete / budget | Met — unit tests |
| Deterministic intake when work prompt present | Met — advance integration |
| `revision` + `STALE_REVISION` on conflicting mutating commands | Met — `test_run_store_durable.py` |
| `run.wait` persisted separately from `status` | Met |
| Atomic snapshot write | Met — temp + rename |
| Idempotent advance at unchanged boundary (no spurious revision bump) | Met — `test_advance_idempotent_without_revision_bump` |

## Verification

From `.cursor/foundry/cli`:

```text
python -m pytest tests/unit/test_advance.py tests/unit/test_run_store_durable.py -q
python -m pytest tests/unit/test_intake_executor.py tests/acceptance/test_shape_*.py -q
```

## Out of scope (later phases)

- Unix socket job host daemon (Phase 3)
- Model adapter dispatch for `wait.kind=agent` (Phase 4)
- User-facing `foundry shape` (Phase 5)
- Full historical run migration tooling
