# Engine DSL runtime hardening

Status: **done** (2026-10-07)  
**As-built:** [implementation-flow-runtime.md](../../features/implementation-flow-runtime.md)  
**Parent:** [engine-dsl-follow-up-plan.md](engine-dsl-follow-up-plan.md)

## Delivered

- Judgment completion via task YAML `advance.complete_action` and ActionRegistry (`visit.*.complete` actions).
- Work-prompt operator waits from `presentation.work_prompt_wait` in operations manifests.
- Matrix `task_bound_boundary_wait` only when `pending_open_questions`; removed dead post-shape fallback branch.
- `RUNTIME_PROFILE_ALLOWED_KEYS` validation in `registry_refs`; `work_prompt_from_snapshot` in `run_config.py`.
- Grep guard unit tests in `test_engine_dsl_guards.py`.

## FINAL verification

| Check | Result |
|-------|--------|
| `just unit` | PASS |
| `just acceptance-shape` | PASS |
| `just acceptance-execute` | PASS |
| `just acceptance-infra` (incl. job_host) | PASS |
| `test_shape_canonical_advance` | PASS |
| `just validate-app` | PASS (exit 0) |
| `just engine-matrix` | PASS |

`just check` requires committed `docs/` after merge.
