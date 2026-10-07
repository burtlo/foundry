# Step 1 — shared runtime prerequisites

Status: **partial** — host/dispatch/idempotency largely delivered; generic executor and F5 replay remain open.  
**Runtime context:** [implementation-flow-runtime.md](../features/implementation-flow-runtime.md).  
**Policy:** [workflow-implementation-policy.md](../features/workflow-implementation-policy.md) §§3–6, §7 F1–F9.

## Delivery checklist

| # | Prerequisite | Status | Evidence / pointer |
| ---: | --- | --- | --- |
| 1 | Host path / ownership | **Delivered** | F6; [job-host-architecture.md](../concepts/job-host-architecture.md) Phases 0–7 |
| 2 | Durable snapshot, ledger, outbox, dispatch, idempotency | **Mostly delivered** | F4, F8 closed; F5 partial (replay) |
| 3 | Strict validation, expressions, checks fail-closed | **Delivered** (REL-006) | Step 0 §3; `test_hooks.py` |
| 4 | Engine + user gate lifecycles, typed evidence, loop counters | **Partial** (REL-005) | `status_reason` / repair+reverify limits; T7/T8 unit |
| 5 | Generic task/operation executor + model adapter | **Delivered** | `MechanismRunner` + `actions.py` host path; `ensure_agent_request` task path; bound `operations.yaml`; [implementation-flow-runtime.md](../features/implementation-flow-runtime.md); [engine DSL plan](archive/engine-dsl-orchestration-plan.md) Steps 5–8 |
| 6 | Shape E2E through `execute.start` | **Partial** | `shape_phase_e2e.feature`; canonical advance: `shape_canonical_advance.feature` |

## Exit (runbook)

Fresh run completes Shape through user CLI; engine gates and routes obey graph contract; remediation acceptance tests pass on default paths.

Implement prerequisites **in the slice** that needs them; do not wait for full Step 1 completion before shipping a targeted feature.
