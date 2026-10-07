# Implementation-flow release charter

Status: **in progress** — contract revision largely **done**; runtime release waves **R-0** through **R-7** **open**.
**Verdict target:** [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md) §F (**COMPLETE**).
**How to run work:** [orchestrator-brief.md](orchestrator-brief.md) + [remaining-nodes-orchestrator-runbook.md](remaining-nodes-orchestrator-runbook.md).

This document **sequences and links** existing plans. It does not restate their requirements.

---

## 1. Governance and inventory

| Document | Role in release |
| --- | --- |
| [README.md](README.md) | Plans index |
| [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md) | Binding policy (Step 0); amend before contract changes |
| [node-inventory.md](node-inventory.md) | Per-node boundary status |
| [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md) | Regenerate after engine changes |
| [workflow-node-revision-orchestration.md](workflow-node-revision-orchestration.md) | Contract revision program (**COMPLETE**) |
| [workflow-node-revision-patterns.md](workflow-node-revision-patterns.md) | Implementer patterns |
| [workflow-node-review-prompt.md](workflow-node-review-prompt.md) | Single-node review method |
| [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md) | Findings **G1–G10**, tests **T1–T10**, legacy slice order §E |

---

## 2. Delivered foundation (no further charter waves)

| Capability | Reference | Notes |
| --- | --- | --- |
| Job host Phases 0–7 | [job-host-architecture.md](../concepts/job-host-architecture.md) | Ledger, advance, dispatch, user CLI |
| `shape.intake` engine path | [shape-deterministic-extraction.md](../shape-deterministic-extraction.md) | No per-node plan file |
| Step 0 policy record | [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md) | Step 1 implementation checkbox still open |
| Engine gate instruction hygiene | [engine-gate-instructions-hygiene-batch.md](engine-gate-instructions-hygiene-batch.md) | **done** |
| Node contract revision (29 nodes) | §3 below | Plan status **done**; runtime gaps remain |

---

## 3. Contract revision track (flow order, authoring)

Per-node cleanup plans describe **judgment vs engine vs steward UX**. They do **not** by themselves close **G1–G10**.

| Order | Node | Plan | Plan status |
| ---: | --- | --- | --- |
| 1 | `shape.intake` | [shape-deterministic-extraction.md](../shape-deterministic-extraction.md) | Delivered |
| 2 | `shape.examine` | [shape-examine-contract-cleanup-plan.md](shape-examine-contract-cleanup-plan.md) | done (slice 7 deferred) |
| 3 | `shape.examine.gate` | [shape.examine.gate-contract-cleanup-plan.md](shape.examine.gate-contract-cleanup-plan.md) | done (paired slices) |
| 4 | `shape.present` | [shape-present-contract-cleanup-plan.md](shape-present-contract-cleanup-plan.md) | done |
| 5 | `shape.present.gate` | [shape-present-gate-contract-cleanup-plan.md](shape-present-gate-contract-cleanup-plan.md) | done (slice 5 deferred) |
| 6 | `shape.record` | [shape.record-contract-cleanup-plan.md](shape.record-contract-cleanup-plan.md) | done |
| 7 | `shape.record.gate` | [shape.record.gate-contract-cleanup-plan.md](shape.record.gate-contract-cleanup-plan.md) | done |
| 8 | `execute.start` | [execute.start-contract-cleanup-plan.md](execute.start-contract-cleanup-plan.md) | done |
| 9 | `execute.intake` | [execute.intake-contract-cleanup-plan.md](execute.intake-contract-cleanup-plan.md) | done |
| 10 | `execute.intake.gate` | [execute.intake.gate-contract-cleanup-plan.md](execute.intake.gate-contract-cleanup-plan.md) | done |
| 11 | `execute.branch` | [execute.branch-contract-cleanup-plan.md](execute.branch-contract-cleanup-plan.md) | done |
| 12 | `execute.plan` | [execute.plan-contract-cleanup-plan.md](execute.plan-contract-cleanup-plan.md) | done |
| 13 | `execute.build` | [execute.build-contract-cleanup-plan.md](execute.build-contract-cleanup-plan.md) | done |
| 14 | `execute.test` | [execute.test-contract-cleanup-plan.md](execute.test-contract-cleanup-plan.md) | done |
| 15 | `execute.test.gate` | [execute.test.gate-contract-cleanup-plan.md](execute.test.gate-contract-cleanup-plan.md) | done |
| 16 | `execute.repair.limit.gate` | [execute.repair.limit.gate-contract-cleanup-plan.md](execute.repair.limit.gate-contract-cleanup-plan.md) | done |
| 17 | `execute.commit` | [execute.commit-contract-cleanup-plan.md](execute.commit-contract-cleanup-plan.md) | done |
| 18 | `execute.commit.gate` | [execute.commit.gate-contract-cleanup-plan.md](execute.commit.gate-contract-cleanup-plan.md) | done |
| 19 | `verify.intake` | [verify.intake-contract-cleanup-plan.md](verify.intake-contract-cleanup-plan.md) | done |
| 20 | `verify.intake.gate` | *(engine gate — render-only; see [engine-gate-instructions-hygiene-batch.md](engine-gate-instructions-hygiene-batch.md))* | done |
| 21 | `verify.acceptance` | [verify.acceptance-contract-cleanup-plan.md](verify.acceptance-contract-cleanup-plan.md) | done |
| 22 | `verify.acceptance.gate` | [verify.acceptance.gate-contract-cleanup-plan.md](verify.acceptance.gate-contract-cleanup-plan.md) | done |
| 23 | `verify.code_quality` | [verify.code_quality-contract-cleanup-plan.md](verify.code_quality-contract-cleanup-plan.md) | done |
| 24 | `verify.code_quality.gate` | [verify.code_quality.gate-contract-cleanup-plan.md](verify.code_quality.gate-contract-cleanup-plan.md) | done |
| 25 | `verify.code_review` | [verify.code_review-contract-cleanup-plan.md](verify.code_review-contract-cleanup-plan.md) | done |
| 26 | `verify.code_review.gate` | [verify.code_review.gate-contract-cleanup-plan.md](verify.code_review.gate-contract-cleanup-plan.md) | done |
| 27 | `verify.complete` | [verify.complete-contract-cleanup-plan.md](verify.complete-contract-cleanup-plan.md) | done |
| 28 | `verify.complete.gate` | [verify.complete.gate-contract-cleanup-plan.md](verify.complete.gate-contract-cleanup-plan.md) | done |
| 29 | `deliver.stub` | [deliver.stub-contract-cleanup-plan.md](deliver.stub-contract-cleanup-plan.md) | done |

**Deferred contract slices (only if acceptance fails):** `shape.examine` slice 7; `shape.present.gate` slice 5 — see respective plans.

---

## 4. Runtime release waves (delivery order)

Execute in order. Verifier must accept wave **N** before **N+1** starts ([orchestrator-brief.md](orchestrator-brief.md)).

| Wave | Name | Primary plan | Closes (gap plan) | Tests (§D) |
| ---: | --- | --- | --- | --- |
| **R-0** | Contract freeze | [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 0 | Policy for **G1**, **G3** | — |
| **R-1** | Kernel honesty | [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 1; [step1-runtime-prerequisites-plan.md](step1-runtime-prerequisites-plan.md) §3–4 | **G8**, **G9** (partial), Step 0 checks | T7, T8 (partial) |
| **R-2** | Verify acceptance as agent task | [agent-adapter-integration-plan.md](agent-adapter-integration-plan.md); gap §C **G1** | **G1** | T1, T5 |
| **R-3** | Manifest build/test + build policy | [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 3; [execute.build](execute.build-contract-cleanup-plan.md) / [execute.test](execute.test-contract-cleanup-plan.md) | **G3** | T9, T1 |
| **R-4** | Advance classifier | [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 2 | Enables **G4**, **G6** without new `advance` branches | per-node acceptance |
| **R-5** | Hold, blocked intake, single paths | Gap §C **G2**, **G5**, **G4**, **G6**; Step 0 §2 | **G2**, **G5**, **G4**, **G6** | T2, T3, T4 |
| **R-6** | Docs, limits, operations stance | [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phases 4–5; gap **G7**, **G10** | **G7**, **G9**, **G10** | — |
| **R-7** | Release integration | [release-integration-plan.md](release-integration-plan.md) | All **G1–G10** | T1–T10 |

**Mapping to gap plan §E (legacy order):** G2 → **R-5** (can start early as a small spike after **R-0**); G1 → **R-2**; G3 → **R-3**; G5/G8 → **R-1** + **R-5**; G4/G6 → **R-4** + **R-5**; G7/G9/G10 → **R-6**; Integration → **R-7**.

---

## 5. Runbook cross-reference

| Runbook section | Charter waves |
| --- | --- |
| Step 0 — baseline and decisions | **R-0** (complete); maintain inventory |
| Step 1 — shared runtime prerequisites | [step1-runtime-prerequisites-plan.md](step1-runtime-prerequisites-plan.md); overlap **R-1**, **R-4** |
| Step 2 — node slices 2A–2F | Superseded for *new* work by **R-2**–**R-7** (host skeleton exists); use per-node plans §3 for acceptance tags only |

---

## 6. Suggested first implementation slices

Same as [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) execution focus:

1. **R-0** — acceptance + receipt typing decisions.
2. **R-2** — `verify.acceptance` agent task (**G1**).
3. **R-4** (pilot) — classifier + one mechanical node (e.g. `execute.branch`).
4. **R-3** — shared manifest command runner + **G3** policy.

Optional parallel: **R-5** spike for **G2** (hold + advance) once **R-0** is written.

## Canonical delivery sequence (REL-001 … REL-019)

Orchestrator slices: one implementer → separate verifier per **REL**; update **Status** when accepted.
Coarse waves **R-0…R-7** remain in §4; this table is the fine-grained queue.
**Policy:** [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md) (frozen at REL-001). **Gaps/tests:** [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md).

| REL | Status | Wave | Depends | Closes | Tests | Work specification |
| ---: | --- | ---: | --- | --- | --- | --- |
| **001** | done | R-0 | — | **G1**, **G3** (policy) | — | Step 0 §12–§14: verify acceptance, receipt kinds, execute host-only scope; no product code. [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 0. |
| **002** | done | R-5 | 001 | **G2** | T2 | `shape.record.gate` **hold** must not complete run on advance; route or `on_hold` status. |
| **003** | done | R-2 | 001 | **G1** | T1, T5 | Bind `verify.acceptance` to agent task (`implementation-validator`); thin gate reads sealed findings. [agent-adapter-integration-plan.md](agent-adapter-integration-plan.md). |
| **004** | done | R-1 | 001 | Step 0 §10, kernel honesty | — | `admit_visit` honors **skip** / **escalate** / **disqualify** ([lifecycle.py](../../.cursor/foundry/cli/foundry_cli/engine/lifecycle.py)). |
| **005** | done | R-1 | 004 | **G8**, **G9** (partial) | T7, T8 (partial) | Loop-scoped `history.count`; `status_reason` / halt reasons; repair & reverify limits. [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 1. |
| **006** | done | R-1 | 001 | Step 1 §3, F3 | — | Strict command checks fail-closed; `test_hooks.py` coverage. [step1-runtime-prerequisites-plan.md](step1-runtime-prerequisites-plan.md). |
| **007** | done | R-4 | 003 | enables **G4**, **G6** | per-node | Advance classifier + dispatch registry; no new per-node `advance.py` branches. [advance_classifier.py](../../.cursor/foundry/cli/foundry_cli/engine/advance_classifier.py). |
| **008** | done | R-4 | 007 | **G4** (partial) | unit + acceptance | Classifier pilot: `execute.branch` as **git/mechanical** step. |
| **009** | done | R-3 | 001, 003 | **G3** (prose + boundary) | T9 | Host-only `execute.build` / `execute.test` steward prose; park boundary per §14. |
| **010** | done | R-3 | 003, 009 | **G1** (adapter path) | T1, T5 | `FOUNDRY_AGENT_ADAPTER`, HTTP contract, registry task builders; production path without verify env override. [agent-adapter-integration-plan.md](agent-adapter-integration-plan.md). |
| **011** | done | R-5 | 001 | **G5** | T3, T4 | Blocked execute/verify intake: operator wait, `request_ref`, reopen/retry recovery. (`blocked_intake.py`). |
| **012** | done | R-5 | 007 | **G4** | — | Worker vs host on `execute.intake`, `verify.intake`, `execute.test`: single path (host-only or agent-wait). |
| **013** | done | R-5 | 007 | **G6** | — | Single canonical Shape present/record path; deprecate or test-only dual steward/host path. |
| **014** | pending | R-1 | 004 | **G7** (partial) | — | Thin engine gate resolvers read sealed check outcomes only ([gates.py](../../.cursor/foundry/cli/foundry_cli/engine/gates.py)). |
| **015** | done | R-6 | 014 | **G7** | — | Regenerate [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md) from `node_capability.audit_rows`; sync [node-inventory.md](node-inventory.md). |
| **016** | done | R-6 | 005 | **G9** | T8 | `execute.commit.gate` reverify limit fail-closed in resolver (not only on_examine). |
| **017** | pending | R-6 | 016 | **G9** (docs/parity) | T8 | Any remaining reverify hook/docs parity vs flow lifecycle (if gaps remain after 016). |
| **018** | pending | R-6 | 015 | **G10** | — | `operations.yaml` stance A/B documented in [node-inventory.md](node-inventory.md). [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 4. |
| **019** | pending | R-7 | 001–018 | **G1–G10** | T1–T10 | [release-integration-plan.md](release-integration-plan.md); full evidence gates; charter **COMPLETE**. |

**Parallelism (after 001):** **002**, **003**, **004**, **006** may run in parallel; **005** after **004**; **007** after **003**; **008** after **007**; **010** after **003**+**009**; **011–013** after **007** (R-5 bundle); **015** after **014**; **019** last.

**Evidence for `done` rows:** `git log --grep='REL-'` → `0b0f68c` (001), `006259a` (002+003), `1bdbb2c` (004), `81b6505` (006), `caafa51` (005), `d6a7713` (007), `6e4162f` (008), `16a1440` (009), `28433e7` (010), `63a46c0` (015), `cf2b51d` (016); REL-011–013 in latest R-5 commit.

---

## 7. Release exit

When [release-integration-plan.md](release-integration-plan.md) verifier accepts:

- Update this charter **Status** to **COMPLETE**.
- Gap plan verdict in §F satisfied.
- [README.md](README.md) points to this charter as the shipped sequencing record.
