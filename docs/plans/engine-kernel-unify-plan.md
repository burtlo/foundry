# Engine kernel unify plan

Status: **active** — structural runtime work for the implementation-flow release.  
**Parent:** [release-charter.md](release-charter.md) — canonical **REL** sequence (waves **R-0**–**R-7** map in charter table).  
**Do not duplicate:** acceptance policy, gap findings, and test IDs live in [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md) and [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md).

## Problem statement

The durable kernel (ledger, lifecycle, hooks, routing, agent validate/apply for bound tasks) is sound. Advancement still encodes a **second workflow** in Python (`advance.py`, `*_step_executor.py`, parallel `_ENGINE_RESOLVERS`) that shadows [registry.yaml](../../.cursor/foundry/flows/implementation/registry.yaml). Node `operations.yaml` is authoring/docgen-only unless explicitly bound.

**Rule for this plan:** no new `if node_id == "…"` in `advance.py`. New behavior = flow check, task YAML + schema, manifest command profile, or class handler registered once.

**Patterns:** [workflow-node-revision-patterns.md](workflow-node-revision-patterns.md). **Inventory:** [node-inventory.md](node-inventory.md).

---

## Phase 0 — Contract freeze (decisions only)

| Item | Authority | Charter wave |
| --- | --- | --- |
| Verify acceptance “criterion met” policy | [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md) §9 item 3, [§12 (G1)](workflow-02-step0-decisions.md#12-verify-acceptance-criterion-policy-g1) | R-0 |
| Receipt kinds: judgment vs engine/mechanical | [workflow-02-step0-decisions.md §13](workflow-02-step0-decisions.md#13-receipt-kinds-judgment-vs-enginemechanical) | R-0 |
| Execute build product choice (enforce vs host-only) | [workflow-02-step0-decisions.md §14 (G3)](workflow-02-step0-decisions.md#14-execute-phase-implementation-scope-g3); gap **G3** | R-0 |

**Exit:** verifier accepts written policy; implementers do not add env-based verify pass or fake `agent-receipt` for new mechanical steps.

---

## Phase 1 — Kernel honesty

| Work | Closes | Detail in |
| --- | --- | --- |
| `skip` / `escalate` / `not_applicable` in `admit_visit` | Step 0 §10, hygiene | [lifecycle.py](../../.cursor/foundry/cli/foundry_cli/engine/lifecycle.py) |
| Loop-scoped `history` (repair / reverify limits) | **G9**, **G8** | gap plan §C G8–G9; [routing.py](../../.cursor/foundry/cli/foundry_cli/engine/routing.py) |
| Thin engine gate resolvers (read sealed check outcomes) | **G7** partial | [gates.py](../../.cursor/foundry/cli/foundry_cli/engine/gates.py) |

**Exit:** unit tests for skip path and repair/reverify at limit; fewer special cases in `verify_step_executor.py`.

**Charter wave:** **R-1**.

---

## Phase 2 — Advance classifier (collapse duplicate dispatch)

Replace per-node switches with a **node classifier** (extend [node_capability.py](../../.cursor/foundry/cli/foundry_cli/engine/node_capability.py)):

| Class | Wait | Advance action |
| --- | --- | --- |
| User gate | `decision` | `gate decide` |
| Engine gate | — | resolve on open/seal via hooks + resolver |
| Task-bound step | `agent` | generic request + applicator registry |
| Manifest command step | — | shared command runner → seal |
| Git/mechanical step | — | branch/commit helpers |

Migrate nodes off `_HOST_IMPLEMENTED_STEP_NODES` one acceptance feature at a time; keep existing executors as backends initially.

**Exit:** new judgment task = task YAML + schema + applicator, not `advance.py` edit.

**Charter wave:** **R-4** (after first feature slices prove backends).

---

## Phase 3 — Features (agents, manifest commands)

| Track | Plan / gap | Charter wave |
| --- | --- | --- |
| `verify.acceptance` as real agent task | **G1**, [agent-adapter-integration-plan.md](agent-adapter-integration-plan.md) | **R-2** |
| Shared build/test/lint from `app.yaml` | **G3**, per-node docs [execute.build](execute.build-contract-cleanup-plan.md), [execute.test](execute.test-contract-cleanup-plan.md) | **R-3** |
| Cursor / HTTP agent adapter | [agent-adapter-integration-plan.md](agent-adapter-integration-plan.md) | **R-3** |
| Host advance pumping (optional) | [job-host-architecture.md](../concepts/job-host-architecture.md) | R-3 follow-up |

**Exit:** one non-stub path toward `deliver.stub` without `FOUNDRY_VERIFY_ACCEPTANCE_DECISION` (gap **T1**, **T5**).

---

## Phase 4 — `operations.yaml` stance

Documented in [node-inventory.md](node-inventory.md) § **`operations.yaml` stance** (REL-018):

- **A (default):** docgen-only; mechanism truth = flow checks + class handlers.
- **B (later):** mechanism schema + interpreter — only after Phase 2; not implemented.

**Charter wave:** **R-6** (documentation + audit; closes gap **G10** with `node_capability` shape judgment registration).

---

## Phase 5 — Expression language

Either narrow [expressions.md](../concepts/expressions.md) to supported fragments (status quo in `evaluate_when_expression`) or implement typed evaluator. No new substring matchers.

**Charter wave:** **R-6** or post-release.

---

## Step 1 runtime prerequisites (overlap)

Shared host/validation/executor work from [remaining-nodes-orchestrator-runbook.md](remaining-nodes-orchestrator-runbook.md) Step 1 is **not** a separate product release; track completion in [step1-runtime-prerequisites-plan.md](step1-runtime-prerequisites-plan.md). Phases 1–2 above subsume the highest-risk Step 1 items (checks, gates, generic task path).

---

## Evidence gates

Per [orchestrator-brief.md](orchestrator-brief.md) and [remaining-nodes-orchestrator-runbook.md](remaining-nodes-orchestrator-runbook.md#evidence-gates-command).
