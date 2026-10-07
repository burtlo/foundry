# Step 1 — shared runtime prerequisites

Status: **partial** — host/dispatch/idempotency largely delivered; checks, expressions, generic executor, and fail-closed hooks remain open.  
**Parent:** [release-charter.md](release-charter.md) (foundation before **R-1**).  
**Procedure:** [remaining-nodes-orchestrator-runbook.md](remaining-nodes-orchestrator-runbook.md) Step 1.  
**Policy:** [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md) §§3–6, §7 F1–F9.

## Delivery checklist

| # | Prerequisite | Status | Evidence / pointer |
| ---: | --- | --- | --- |
| 1 | Host path / ownership | **Delivered** | F6; [job-host-architecture.md](../concepts/job-host-architecture.md) Phases 0–7 |
| 2 | Durable snapshot, ledger, outbox, dispatch, idempotency | **Mostly delivered** | F4, F8 closed; F5 partial (replay) |
| 3 | Strict validation, expressions, checks fail-closed | **Delivered** (REL-006) | Step 0 §3; `test_hooks.py` |
| 4 | Engine + user gate lifecycles, typed evidence, loop counters | **Partial** | Step 0 §§5, 9; [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 1 |
| 5 | Generic task/operation executor + model adapter | **Open** | Step 0 §6; [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 2–3 |
| 6 | Shape E2E through `execute.start` | **Partial** | `shape_phase_e2e.feature`; gap **G6** |

## Exit (runbook)

Fresh run completes Shape through user CLI; engine gates and routes obey graph contract; remediation acceptance tests pass on default paths.

**Do not block** charter waves **R-2**/**R-3** on full Step 1 completion; implement prerequisites **in the slice** that needs them (orchestrator rule in [orchestrator-brief.md](orchestrator-brief.md)).
