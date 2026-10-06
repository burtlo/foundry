# Plan: `shape.examine` contract cleanup

Status: **done** (slices 1–6; slice 7 deferred)

Related: [workflow node review prompt](workflow-node-review-prompt.md) (methodology), [shape-deterministic-extraction.md](../shape-deterministic-extraction.md), completed intake pattern in [nodes/shape.intake.md](../nodes/shape.intake.md), generated [nodes/shape.examine.md](../nodes/shape.examine.md).

## Goal

`shape.examine` is a **judgment-bounded step with an engine-owned completion path**: the model produces one structured `ShapeExaminationResult` per examination round; Foundry validates, patches state, manages the clarifying-question loop, seals the agent receipt, and routes to `shape.present` or `shape.examine.gate`.

Align with the responsibility model:

| Layer | Owner |
|-------|--------|
| **Judgment** | Model task `shape.examine` (`judgment.md` + `shape-examination-result.schema.json`) |
| **Mechanism** | Engine: `apply_examination_result`, waits, `run_shape_examine_complete`, connection `when:` |
| **Policy** | `prior-shape-intake-sealed`, `agent-receipt-sealed`, derived `open_clarifying_questions_count` at transition |
| **Presentation** | Gate prompt on `shape.examine.gate`; steward chat for answers — not receipt routing prose in judgment |

Happy path:

```
enter shape.examine → agent wait → run agent submit (result) → [user_input wait + answer if questions]
  → visit examine complete (or run advance) → seal + transition → present or examine.gate
```

**Testing principle:** Unit tests prove engine behavior; feature tests (`@node.shape.examine`) prove CLI + snapshot + ledger against the **target flow schema**. Remove acceptance scenarios that certify the legacy manual `state_patch` → write `agent.json` → `receipt seal` → `transition` chain as the product contract.

## Non-goals

- Generic `operations.yaml` executor for all nodes (workflow-wide Step 1) — unless this slice only adds **examine-specific** wiring behind `visit examine complete`.
- Redesigning `shape.examine.gate`, `shape.present`, or `shape.present.gate`.
- Replacing the agent task with a subagent file under `.cursor/agents/`.
- Conversational examination outside structured `questions` / `answer` (no expansion of `allow.user.ask` semantics in this plan).
- Materializing `reads.artifacts` `nearest_sealed_ancestor` in the context packet (optional follow-up slice; document gap until shipped).

## Prerequisites

- **`shape.intake` contract cleanup** should land first or in parallel: examine admission depends on sealed intake; stale `state.ticket` on reshape loops is an intake concern but examine tests must tolerate the intake target contract.

## Current gaps (from node review)

| Area | Problem |
|------|---------|
| **Dual completion paths** | Production uses `advance` + `run_shape_examine_complete`; acceptance tests use steward `visit state patch`, manual `agent.json`, `receipt seal`, `transition`. |
| **Schema `allow.cli`** | Exposes `ledger.show`, `receipt.link`, `transition`, `visit.state_patch` — duplicates engine completion and lets stewards bypass agent/state derivation. |
| **Schema `allow.files.write`** | Steward may write `run:receipts/agent.json` though engine builds receipt from accepted result on auto-complete. |
| **`allow.user.ask: true`** | Overlaps structured `questions` + `answer` / `user_input` wait; unclear product semantics. |
| **`questions_asked_total`** | Declared in `reads` / `allow.state` but **never updated** by engine — dead contract surface. |
| **`operations.yaml`** | Describes mechanism (`patch_examination_state`, seal, transition) that is **not executed**; duplicates `submit.py`, `shape_step_executor.py`, and flow connections. |
| **`judgment.md`** | Still narrates host routing (fast lane vs gate) — orchestration that belongs in engine/docs only. |
| **Routing metadata** | `run_shape_examine_complete` sets agent receipt `recommended_next_state: shape.present` even when routing goes to `shape.examine.gate`. |
| **Transition trust** | Steward can patch `open_clarifying_questions_count` without matching `clarifying_questions` (manual path); no enforcement at `transition_visit`. |
| **Task input** | `prior_answers` built from `clarifying_questions` only; `clarifying_answers` map not merged into task input (may be OK if questions carry `answer` after submit — verify and document). |
| **Agent submit capability** | `run agent submit` exists globally but is **not** listed on node `allow.cli`; contract unclear for stewards vs host-only. |
| **No `visit examine complete`** | Unlike intake, no single semantic CLI for seal + transition after judgment. |
| **Docs vs code** | `doc.yaml` says steward **none at runtime**; flow YAML still grants full manual orchestration. |

## Target contract (summary)

### Flow node (`factory-flow.yaml`)

```yaml
# Target shape — illustrative; field order may match catalog conventions
- id: shape.examine
  kind: step
  title: Shape examination — draft AC and clarifying questions
  produces:
    artifacts: []
  instructions: registry:nodes/shape.examine/judgment.md
  reads:
    config:
      - foundry.shape
    state:
      - ticket
      - clarifying_questions
      - examination_round
      - open_clarifying_questions_count
      - examination_decisions
      - assumptions
      - draft_ac
    artifacts:
      - artifact: shape.intake.ticket
        from: nearest_sealed_ancestor
  allow:
    cli:
      - run.agent.submit
      - visit.examine.complete
    user:
      ask: false
  lifecycle:
    on_examine:
      - check: prior-shape-intake-sealed
    on_seal:
      - check: agent-receipt-sealed
        on_fail:
          action: reopen
          reason: Examination not ready to seal
  receipts: registry:schemas/agent-receipt.schema.json
```

**Removed from node entry (intended):**

- `operations:` on flow YAML (see [Operations manifest](#operations-manifest)).
- `allow.cli`: `ledger.show`, `receipt.link`, `transition`, `visit.state_patch`.
- `allow.files.write` for `run:receipts/agent.json`.
- `allow.state` patches for examination domain fields (engine sets via `apply_examination_result` and answer handler).
- `reads.state.questions_asked_total` and `allow.state.questions_asked_total` unless implemented in engine (preferred: **remove**).
- `allow.user.ask: true` (use `answer` when `wait.kind=user_input`; document in craft command).

**Kept / clarified:**

- `instructions` → `judgment.md` (minimal judgment-only prose).
- `reads.state.approved_ac` on refine re-entry from `shape.present.gate` — keep if present gate reject routes back with approved/presented context; otherwise trim to what `build_shape_examine_input` actually needs.

**Decision points (record in PR):**

1. **`visit examine complete` vs advance-only:** Mirror intake: expose `visit examine complete` for stewards/scripts; `run advance` calls the same executor when visit is opened and a non-superseded accepted result exists with `open_clarifying_questions_count == 0` (and optionally when gate path is intentional — see policy below).
2. **Gate path with open questions:** Product rule: after agent result with open questions, user may (a) answer via `answer` and re-run judgment, or (b) proceed to `shape.examine.gate` without answering. Today manual `transition` with `open_clarifying_questions_count != 0` reaches the gate; agent path blocks advance on `user_input` wait. **Choose one policy** and test it:
   - **Recommended:** Allow `visit examine complete` only when either `open_clarifying_questions_count == 0` **or** steward explicitly passes `--with-open-questions` (gate path); answering all questions remains the default loop before complete.
3. **Engine-privileged writes:** `visit examine complete` and `run agent submit` must seal receipts / patch state without steward `allow.files.write` (same pattern as intake complete).

### Judgment file (`nodes/shape.examine/judgment.md`)

Target content (~15–25 lines):

- Purpose: interpret ticket + prior Q&A (+ project context in task input).
- Output: schema-bound fields only (`draft_acceptance_criteria`, `assumptions`, `questions`, `decisions`, `summary`).
- Explicit: do not call CLI; do not choose next node.

Remove: host routing bullets, receipt sealing narration.

### Operations manifest

**Option A (recommended):** Remove `operations` from flow YAML; keep `nodes/shape.examine/operations.yaml` as **author-only** in `doc.yaml` / docgen execution notes, or replace body with:

```yaml
version: 1
node_id: shape.examine
note: Mechanism implemented in submit.py, examination_state.py, shape_step_executor.run_shape_examine_complete, advance.py
```

**Option B:** Retain `operations` key for catalog; strip `mechanism` steps to avoid implying runtime execution.

Do not maintain a parallel executable spec until the generic executor exists.

### Schema as test oracle

| Schema element | What tests must prove |
|----------------|----------------------|
| `instructions` | `run context` inlines judgment; path resolves to `judgment.md`. |
| `allow.cli` | Only `run.agent.submit` and `visit.examine.complete` succeed on opened visit; removed caps return `CAPABILITY_DENIED`. |
| `allow.user.ask` | `false` or absent; clarifying flow uses `answer` / host `run.answer`. |
| No `allow.files.write` | Steward cannot write `agent.json`; engine writes on complete. |
| `lifecycle.on_examine` | Without sealed intake → halted at `examined` (`shape_examine.feature` scenario retained). |
| `lifecycle.on_seal` | Transition without sealed agent receipt → `CHECK_FAILED` / reopen. |
| Routing | `open_clarifying_questions_count == 0` → `shape.present`; `!= 0` → `shape.examine.gate` (after complete). |
| Agent path | Submit valid result → state patched; open questions → `user_input` wait; answers → supersede + new agent wait (`test_examination_round.py`). |
| Advance | After accepted result and zero open questions, `advance_run_durable` seals and transitions without steward transition. |

## Testing strategy

### Layers

| Layer | Location | Role |
|-------|----------|------|
| **Unit** | `test_examination_state.py`, `test_examination_round.py`, `test_agent_connection.py`, `test_shape_cli.py`, `test_advance.py`, `test_engine.py` (capabilities), `test_node_operations.py` | Waits, supersede, submit, complete executor, denials. |
| **Feature** | `shape_examine.feature`, `run_context.feature`, `shape_phase_e2e.feature`, `catalog_build.feature` | CLI contract, context allow list, phase composition. |

Tag: `@node.shape.examine`.

### Rules

1. **Schema-first:** Update `factory-flow.yaml`, then feature tables and unit assertions in the same change set.
2. **No manual path as contract:** Scenarios that only pass via steward `transition` + manual receipt on examine are quarantined or rewritten to `run agent submit` + `visit examine complete` / `run advance`.
3. **Pair critical paths:** Fast lane (no questions), gate path (open questions), receipt reopen, capability denied, on_examine halt — feature coverage where steward-facing; supersede round — unit + at least one feature or e2e.

### Commands

```bash
# From .cursor/foundry/cli
pytest tests/unit/test_examination_state.py tests/unit/test_examination_round.py tests/unit/test_agent_connection.py tests/unit/test_advance.py -q -k "examine or examination"
pytest tests/acceptance/test_shape_examine.py -q
# Phase composition:
pytest tests/acceptance/test_shape_phase_e2e.py -q
```

## Implementation slices

Execute in order; each slice should leave unit and feature tests green.

### Slice 1 — Schema and registry

**Files**

- `.cursor/foundry/flows/factory-flow.yaml` — node block per target contract.
- `.cursor/foundry/nodes/shape.examine/judgment.md` — trim to judgment-only.
- `.cursor/foundry/nodes/shape.examine/doc.yaml` — align ownership; note dual-path removal.
- Remove or author-only `operations` per [Operations manifest](#operations-manifest).
- Regenerate `.cursor/foundry/catalog/nodes/shape.examine.index.yaml`, `docs/nodes/shape.examine.md`.

**Tests**

- `catalog_build.feature` — allow.cli, reads, no stale `operations` in index if removed.
- `run_context.feature` — `shape.examine` scenario: allow list, instructions path, no file write URIs.

### Slice 2 — `visit examine complete` CLI

**Files**

- `foundry_cli/constants.py` — `CAP_VISIT_EXAMINE_COMPLETE = "visit.examine.complete"`.
- `foundry_cli/parser.py` — `visit examine complete` subcommand (mirror intake flags: `--run`, `--visit`, `--summary`, `--revision`, optional `--with-open-questions` if policy chosen).
- `foundry_cli/commands.py` — `cmd_visit_examine_complete` → `run_shape_examine_complete` with capability check.
- `foundry_cli/cli_docgen.py` — document command.
- `foundry.py` — dispatch table entry.

**Behavior**

- Require non-superseded accepted `shape.examine` result for visit (same guard as advance auto-complete).
- Enforce open-question policy before transition (see decision point 2).
- Engine writes and seals `run:receipts/agent.json` without steward file allow.

**Tests**

- **Unit:** `test_intake_executor.py` pattern — new `test_shape_examine_complete.py` or extend `test_shape_cli.py` for happy path, `JUDGMENT_MISSING`, wrong node.
- **Feature:** Replace manual seal/transition scenarios in `shape_examine.feature` with submit + `visit examine complete`.

### Slice 3 — Capability enforcement

**Files**

- `foundry_cli/commands.py` — `_require_capability` on all mutating visit commands (already partial).
- Add capability check for `run agent submit` when active visit is `shape.examine` (if not already enforced in `submit_agent_result_durable`).

**Behavior**

- Deny `visit.state_patch`, `transition`, `receipt.link`, `ledger.show` on opened `shape.examine`.
- Allow `run.agent.submit` only while `wait.kind == agent` (and visit match).

**Tests**

- **Unit:** capability denials per removed CLI.
- **Feature:** one scenario per denied capability or examples table.

### Slice 4 — Executor and policy hardening

**Files**

- `foundry_cli/engine/shape_step_executor.py` — `run_shape_examine_complete`:
  - Set `recommended_next_state` from routing rule (`shape.present` vs `shape.examine.gate`) or omit field.
  - Optionally re-validate `open_clarifying_questions_count` from `clarifying_questions` before transition (reject mismatch with `OPEN_QUESTIONS_MISMATCH`).
- `foundry_cli/engine/submit.py` (`apply_examination_result`) — remove reliance on steward-patched counter; always `sync_open_clarifying_questions_count`.
- `foundry_cli/engine/examination_state.py` — document or fix task input: merge `clarifying_answers` into `build_shape_examine_input` if question objects lack `answer` text.
- `foundry_cli/engine/advance.py` — call shared complete helper; align wait boundaries with Slice 2 policy.
- `foundry_cli/engine/transition_policy.py` — optional: block steward `transition` on examine if any code path still exposes it globally.

**Tests**

- **Unit:** counter derivation vs manual mismatch; receipt `recommended_next_state`; gate vs present routing.
- **Unit:** `test_examination_round.py` unchanged contract for supersede (regression).

### Slice 5 — Feature suite refactor

**Files**

- `tests/acceptance/features/shape_examine.feature` — map every scenario to [Schema as test oracle](#schema-as-test-oracle).
- `tests/acceptance/steps/shape_examine.py` — remove `write examine agent receipt` as default path; add helpers for stub submit + examine complete.
- `tests/acceptance/features/shape_phase_e2e.feature` — use new completion path after intake cleanup.

**Keep**

- `on_examine` failure / halted at `examined`.
- Routing to `shape.present` vs `shape.examine.gate`.
- `VISIT_NOT_OPENED` when lifecycle not opened.

**Remove / rewrite**

- Scenarios whose primary assertion is manual `receipt seal` + `visit transition` without agent submit.

### Slice 6 — Documentation and product commands

| File | Action |
|------|--------|
| `.cursor/commands/craft-shape.md` | After intake: agent judgment via task; `run agent submit`; clarifying `answer`; `visit examine complete` or `run advance`; no manual receipt/transition at examine. |
| `.cursor/rules/node-instructions.mdc` | Add **shape.examine** row: engine completes; judgment in `judgment.md` only; no ledger/show transition fences on this node. |
| `docs/shape-deterministic-extraction.md` | Mark examine contract cleanup; update as-built sequence diagram. |
| `docs/v1-spec.md` | Examine: task + engine complete (not steward orchestration). |
| `docs/plans/node-inventory.md` | Boundary status for `shape.examine`: implemented / agent-task. |
| [shape-deterministic-extraction.md](../shape-deterministic-extraction.md) | Note examine cleanup when intake section is updated. |

### Slice 7 — Optional follow-ups

- Materialize `reads.artifacts` ticket in context packet (`context.py` / artifact resolver).
- Implement `questions_asked_total` increment on new questions in `apply_examination_result` **only if** a downstream consumer needs it; otherwise delete from schema everywhere.
- Host protocol: ensure `run.examine.complete` alias if host prefers RPC symmetry with intake.

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | Happy path (no open questions): agent submit → `visit examine complete` → sealed agent receipt → `shape.present` opened. |
| AC2 | Gate path: agent submit with questions → complete with gate policy → `shape.examine.gate` opened. |
| AC3 | `run context` `allow.cli` lists only `run.agent.submit` and `visit.examine.complete` (plus documented read-only globals). |
| AC4 | Steward cannot `visit state patch` examination fields or write `agent.json` on this node. |
| AC5 | `judgment.md` contains no routing or seal/transition instructions. |
| AC6 | `open_clarifying_questions_count` at transition matches derived count from `clarifying_questions` (or complete rejects). |
| AC7 | Clarifying answer flow supersedes prior result and re-enters agent wait (existing F2 behavior). |
| AC8 | `advance_run_durable` auto-completes examine when judgment accepted and zero open questions (no steward `transition`). |
| AC9 | Catalog index and `docs/nodes/shape.examine.md` match flow YAML after regen. |
| AC10 | No feature scenario requires steward `receipt seal` + `transition` on `shape.examine` as the primary contract. |
| AC11 | Unit + feature tests updated in same PR as schema changes. |

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| External scripts use manual examine transition | Grep docs/examples; deprecation note; short dual-allow window only if required. |
| Gate path policy change confuses users | Document in craft-shape; gate prompt unchanged; explicit `--with-open-questions` flag. |
| `run agent submit` without node allow breaks host | Add allow + test; host may use engine privilege documented in PR. |
| Intake cleanup not merged | Coordinate reads; examine e2e depends on `visit intake complete`. |
| Removing `operations` breaks catalog | Option B stub file. |
| Tests relied on manual receipt JSON | Rewrite fixtures to use submit + complete. |

## Suggested PR breakdown

1. **PR1 — Contract + context tests:** factory-flow node block, judgment trim, operations author-only, regen catalog/docs, `run_context` + `catalog_build`.
2. **PR2 — `visit examine complete` + capability denials + feature refactor.**
3. **PR3 — Executor hardening (counter, recommended_next_state) + unit depth.**
4. **PR4 — craft-shape, rules, v1-spec, extraction doc.**

Prefer fewer PRs if CI stays green throughout.

## Verification checklist (before merge)

- [ ] Target `shape.examine` block in `factory-flow.yaml` matches this plan (or documented delta)
- [ ] **Unit:** examination, advance, agent submit, complete executor tests pass
- [ ] **Feature:** `test_shape_examine.py`, `run_context` examine scenario, phase e2e pass
- [ ] `node-inventory.md` updated
- [ ] `craft-shape.md` describes examine without manual seal/transition
- [ ] Grep: no tests assert removed `allow.cli` / file write URIs for examine
- [ ] `foundry dev acceptance` for `@node.shape.examine` (or project equivalent)

## Reference: implementation map (today)

| Concern | Location |
|---------|----------|
| Judgment task input | `engine/agent/tasks.py` (`build_shape_examine_input`) |
| Result → state | `engine/agent/submit.py` (`apply_examination_result`) |
| Agent wait / dispatch | `engine/advance.py`, `engine/agent/dispatch.py` |
| Clarifying answers | `engine/examination_state.py` |
| Complete (seal + transition) | `engine/shape_step_executor.py` (`run_shape_examine_complete`) |
| Routing | `flows/factory-flow.yaml` connections `when:` |
| Task definition | `.cursor/foundry/tasks/shape.examine.yaml` |
| Output schema | `.cursor/foundry/schemas/shape-examination-result.schema.json` |
| Node assets | `.cursor/foundry/nodes/shape.examine/` (`judgment.md`, `doc.yaml`) |
| Acceptance | `tests/acceptance/features/shape_examine.feature` |
