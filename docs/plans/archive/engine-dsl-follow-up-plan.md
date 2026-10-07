# Engine DSL follow-up plan

Status: **done** (2026-10-07)  
**As-built:** [implementation-flow-runtime.md](../../features/implementation-flow-runtime.md)  
**Parent:** [engine-dsl-orchestration-plan.md](engine-dsl-orchestration-plan.md)

## Delivered

- `runtime.advance` and optional runtime flags drive `resolve_advance_mode` and `NodeRuntimeProfile`.
- Removed `_HOST_ADVANCE` frozensets from `advance_classifier.py`; matrix labels from profile.
- Bound `shape.present` / `shape.record` operations manifests; matrix warnings cleared.
- Generic task-bound advance via `task_bound_advance.py` and task YAML `advance` metadata.
- Cross-platform `just help` (quoted echo lines).

## FINAL verification

| Check | Result |
|-------|--------|
| `just unit` | PASS |
| `just acceptance-shape` | PASS |
| `just validate-app` | PASS (exit 0) |
| `just engine-matrix` / matrix drift test | PASS |
| `advance_classifier` frozensets | PASS (removed) |

`just check` requires a clean `git status` for `docs/` after commit.

Residual gaps addressed in [engine-dsl-runtime-hardening-plan.md](engine-dsl-runtime-hardening-plan.md).
