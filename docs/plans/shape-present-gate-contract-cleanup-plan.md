# Plan: `shape.present.gate` contract cleanup

Status: **done** (Slices 1–4 shipped; Slice 5 deferred — `shape.record` reuse of resolver not in this change.)

Related: [workflow node review prompt](workflow-node-review-prompt.md) (methodology), upstream [shape-present-contract-cleanup-plan](shape-present-contract-cleanup-plan.md) (**done**), sibling pattern [shape.examine.gate](../nodes/shape.examine.gate.md), generated [nodes/shape.present.gate.md](../nodes/shape.present.gate.md).

## Goal

`shape.present.gate` is a **user-decider gate with no model worker**: the engine admits the visit, enforces prerequisites, presents options, validates `gate decide`, seals the visit, and routes by decision. The steward (shape parent agent) performs **presentation-only** chat on turn 1 and proxies the user’s **reject** or **accept** on turn 2.

| Layer | Owner |
|-------|--------|
| **Judgment** | **User** — semantic choice to refine via examination or proceed to record AC |
| **Mechanism** | Engine: `prior-present-sealed`, `gate.presented`, `decide_gate`, `_seal_visit_and_route`, connection `on.decisions` |
| **Policy** | `INVALID_GATE_DECISION`, `GATE_USE_DECIDE` (no `visit transition` on gates), `prior-present-sealed` halt, opened-only decide |
| **Presentation** | Steward two-turn UX (`steward-ux.mdc`); optional engine markdown blurb in `run context` |

Happy path:

```
shape.present sealed → admit shape.present.gate → on_examine (prior-present-sealed) → on_open / gate.presented
  → Turn 1: steward shows full presentation + verbatim presented_ac → STOP
  → Turn 2: user reject|accept → gate decide → sealed → shape.examine | shape.record
```

**Testing principle:** Feature tests (`@node.shape.present.gate`) prove routing, policy halts, and context contract. Unit tests only if context/render or artifact resolution changes. Do not add agent-receipt or steward orchestration scenarios — gates produce a decision only.

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** No worker, no task, no `judgment.md`. Semantic judgment is the **user’s** reject/accept, not an LLM task.

## Non-goals

- Redesigning `shape.record`, `shape.examine`, `shape.present`, or other gates (`shape.record.gate`, `shape.examine.gate` behavior changes beyond **paired consistency** where this slice touches shared helpers).
- Adding `allow.cli` for `gate decide` on the node schema (decider capability is engine-global for user gates; keep minimal `allow.user.decide`).
- Introducing a model worker to “summarize” or re-judge the plan.
- Whole-workflow gate framework redesign or generic `operations.yaml` for gates.
- Refactoring connection metadata in `flows/implementation/registry.yaml` beyond documenting current `reject` → `shape.examine`, `accept` → `shape.record`.

## Prerequisites

- **`shape.present` contract cleanup (done)** — gate admission receives reliable `presented_ac`, `presentation_artifact_path`, and sealed `shape.present.presentation` from upstream.

## Investigation summary (Steps 1–2 distilled)

### Runtime sequence (verified)

1. `shape.present` seals → connection to `shape.present.gate`.
2. Visit admitted → `on_examine` runs `prior-present-sealed` (run **halted** at `examined` if `shape.present` not sealed completed).
3. `on_open` → lifecycle `opened`; engine emits `gate.presented` with options + flow `prompt` (`lifecycle.py`).
4. Steward loads `run context --markdown`; instructions inlined from `nodes/shape.present.gate/instructions.md`.
5. **Two-turn UX** (steward-ux): Turn 1 — full presentation + verbatim `presented_ac`; Turn 2 — `gate decide --decision reject|accept`.
6. `decide_gate` (`gates.py`): validates options, records decision, `_seal_visit_and_route`.
7. Routing: **reject** → `shape.examine`; **accept** → `shape.record` (connections with `on.decisions`).

### Current flow registry node (reference)

```yaml
  - id: shape.present.gate
    kind: gate
    title: Plan presentation — refine or record acceptance criteria
    instructions: registry:nodes/shape.present.gate/instructions.md
    reads:
      state:
      - presented_ac
      - presentation_artifact_path
      artifacts:
      - artifact: shape.present.presentation
        from: nearest_sealed_ancestor
    produces:
      options:
      - reject
      - accept
    prompt: Succinct plan presentation shown. Reject to return to examination, or accept to record acceptance criteria.
    lifecycle:
      on_examine:
      - check: prior-present-sealed
    decider: user
    allow:
      user:
        decide: true
```

### Inputs / outputs / consumers

| When gate opens | Source |
|-----------------|--------|
| `presented_ac` | State patched by `shape.present` complete |
| `presentation_artifact_path` | State (run URI to `presentation.md`) |
| `shape.present.presentation` | Sealed ancestor visit artifact (logical ref) |

| On successful gate close | Output |
|--------------------------|--------|
| Visit sealed, outcome `completed` | Ledger + routing |
| Decision `reject` \| `accept` | Connection selection |

| Consumer | Uses |
|----------|------|
| `shape.examine` (reject path) | Re-entry for refinement; may read prior shape state |
| `shape.record` (accept path) | `presented_ac`, `presentation_artifact_path`, nearest sealed presentation artifact |

### Comparison to `shape.examine.gate`

Nearly identical schema and instructions pattern (two-turn, `allow.user.decide` only, no `allow.cli`). Differences worth pairing in cleanup:

| Topic | `shape.examine.gate` | `shape.present.gate` |
|-------|----------------------|----------------------|
| Turn 1 content | State-only (`draft_ac`, questions, assumptions) | Presentation file + `presented_ac` |
| `reads.artifacts` | None | `shape.present.presentation` / `nearest_sealed_ancestor` |
| `foundry-invoke` fences | `gate decide` **without** `--json` | `gate decide` **with** `--json` |
| Context markdown | State values in `## Reads` table | Same for `presented_ac`; **presentation body not in packet** |

## Current gaps

| Area | Problem |
|------|---------|
| **Artifact read not materialized** | `_reads_block` in `context.py` deep-copies artifact **declarations** only — no `resolved_uri`, no file body. Steward instructions say read from `presentation_artifact_path` **or** artifact; packet does not guarantee either is usable without extra disk reads. |
| **Dual source ambiguity** | Instructions allow path OR artifact; engine should prefer **one canonical source** in the markdown packet (mirror `shape.present` post-cleanup: state + presentation content visible to steward). |
| **No render helper for gate body** | `render.py` adds `## Presentation` blurb for `shape.present` step only — no `## Plan presentation` (or inlined markdown) for this gate. |
| **`nearest_sealed_ancestor` unimplemented** | Grep shows no engine resolver for `from: nearest_sealed_ancestor` in CLI; catalog/docs imply behavior that context assembly does not perform. |
| **Instruction fence inconsistency** | `present.gate` uses `--json` on `gate decide`; `examine.gate` does not — stewards and docs should agree (global `--json` convention). |
| **`doc.yaml` status** | Authoring file still **draft**; sequence diagram omits two-turn STOP (shows single ask/decide). |
| **`node-instructions.mdc`** | Rows for intake/examine/present steps; **no gate row** for two-turn present gate (steward-ux references pattern only). |
| **Generated docs** | `docs/nodes/shape.present.gate.md` draft; permissions table shows empty `allow` (correct) but gaps section may understate artifact resolution gap until fixed or documented. |

**Not gaps (keep as-is):**

- Minimal `allow`: only `allow.user.decide` — correct; no steward `allow.cli`.
- No dedicated executor — `gates.py` + `lifecycle.py` own behavior.
- `instructions.md` (~57 lines) appropriate for gate UX; **no** split to `judgment.md` per `node-instructions.mdc` (gates keep `instructions.md`).
- Existing acceptance: `shape_present_gate.feature`, `run_context.feature` present-gate scenario, `prior-present-sealed` halt fixture.

## Target contract

### Flow node (`flows/implementation/registry.yaml`)

**Illustrative target — expect small or zero YAML delta** after cleanup; schema is already minimal.

```yaml
- id: shape.present.gate
  kind: gate
  title: Plan presentation — refine or record acceptance criteria
  instructions: registry:nodes/shape.present.gate/instructions.md
  reads:
    state:
      - presented_ac
      - presentation_artifact_path
    artifacts:
      - artifact: shape.present.presentation
        from: nearest_sealed_ancestor
  produces:
    options:
      - reject
      - accept
  prompt: Succinct plan presentation shown. Reject to return to examination, or accept to record acceptance criteria.
  lifecycle:
    on_examine:
      - check: prior-present-sealed
  decider: user
  allow:
    user:
      decide: true
```

**Do not add:** `allow.cli`, `worker`, `receipts`, `allow.state`, `allow.files.write`, or `operations` on the flow entry.

**Optional schema clarification (only if implementing resolver):** document in catalog that `reads.artifacts[].from: nearest_sealed_ancestor` is resolved at context-build time to `{ resolved_uri, resolved_path }` (and optionally inlined body in markdown) — no new YAML keys required if resolution is engine behavior.

### Steward instructions (`instructions.md`)

Target: **≤ 80 lines**; two-turn contract unchanged; Turn 1 cites **packet sections** as canonical (not “read file yourself unless missing”).

- Turn 1: Header → **Presentation** (from inlined `## Plan presentation` or `reads.state` + resolved artifact) → verbatim `presented_ac` → STOP line.
- Turn 2: `gate decide` with decision from `produces.options`; align `foundry-invoke` fences with project convention (`--json` on both shape gates or neither — **recommend both** for steward-ux JSON workflows).

### Engine / context (if slice ships)

1. **Resolve presentation for gate context** — in `assemble_context` and/or `render_context_markdown`:
   - Resolve `presentation_artifact_path` from state to disk path when present.
   - Resolve `shape.present.presentation` to the sealed ancestor visit’s `presentation.md` URI (shared helper with future `shape.record` / archive readers).
   - Prefer single source: path from state if it matches sealed artifact; else resolved ancestor URI.
2. **Markdown section** — for `node_id == "shape.present.gate"`, append `## Plan presentation` with full markdown body (same spirit as `## Presentation` blurb on `shape.present` step — but **content**, not CLI narration).

**Decision points (record in PR):**

1. **Inline body vs resolved path only:** **Recommend inline body** in markdown context when file exists; fall back to path + warning when missing (fail-soft for stewards, strict tests on fixtures).
2. **`nearest_sealed_ancestor` scope:** Implement minimally for `shape.present.presentation` in this slice vs shared `context.py` helper used later by `shape.record` context — **recommend shared helper** with unit tests.
3. **`--json` on gate decide fences:** Add to `shape.examine.gate/instructions.md` for parity (not remove from present gate).

## Instruction audit (`instructions.md`)

| Section | Classification | Action |
|---------|----------------|--------|
| **Goal** (record user decision) | **POLICY** / presentation | **KEEP** — orients steward; no routing ids |
| **Two-turn minimum** | **POLICY** | **KEEP** — matches steward-ux |
| **Turn 1 — Header** | **PRESENTATION** | **KEEP** |
| **Turn 1 — read presentation from path OR artifact** | **ENGINE** (should be packet) | **ENGINE** — replace with “render full body from steward context `## Plan presentation` or `reads` tables”; delete dual-source OR prose after render ships |
| **Turn 1 — verbatim `presented_ac`** | **PRESENTATION** | **KEEP** — user must see exact AC text |
| **Turn 1 — STOP line** | **POLICY** | **KEEP** |
| **Turn 1 — do not gate decide / AskQuestion** | **POLICY** | **KEEP** |
| **Turn 2 — re-run Turn 1 if summarized** | **POLICY** | **KEEP** |
| **Turn 2 — gate decide fences** | **MECHANISM** | **KEEP**; normalize `--json` with examine.gate |
| **Boundaries** (no transition, worker, artifacts, state patch) | **POLICY** | **KEEP** |

No **DELETE** of entire file; no **judgment.md** fork.

## Testing strategy

### Layers

| Layer | Location | Role |
|-------|----------|------|
| **Unit** | New or extended tests for context artifact resolution (e.g. `test_context.py`, `test_render.py`) | Resolver + markdown section when presentation file exists |
| **Feature** | `shape_present_gate.feature`, `run_context.feature`, `shape_phase_e2e.feature`, `job_host.feature` | Routing, halt, context fields, markdown content |
| **Regression** | `gates.py` behavior | Only if touching decide path (unlikely) |

Tag: `@node.shape.present.gate`.

### Schema as test oracle

| Schema element | What tests must prove |
|----------------|----------------------|
| `kind: gate`, `decider: user` | `gate decide` works; `visit transition` → `GATE_USE_DECIDE` |
| `produces.options` | `reject` / `accept` route to `shape.examine` / `shape.record` |
| `allow.user.decide` | Context `allow user decide is true`; decide denied if false (if covered elsewhere) |
| No `allow.cli` | Context `allow cli` empty for this node (existing scenario) |
| `lifecycle.on_examine` | `prior-present-sealed` → halted run without sealed present |
| `reads.state` | Context includes `presented_ac`, `presentation_artifact_path` with fixture values |
| `reads.artifacts` | Declaration present in JSON context; **after slice:** resolved URI and/or markdown contains presentation body |
| `prompt` | Matches flow string in JSON context |
| `instructions` | Inlined in markdown; two-turn headings; no `## Judgment` |

### Commands

```bash
# From .cursor/foundry/cli
pytest tests/acceptance/test_shape_present_gate.py tests/acceptance/test_run_context.py -q -k "present_gate or present.gate"
pytest tests/unit -q -k "context or render"  # after resolver slice
pytest tests/acceptance/test_shape_phase_e2e.py -q
```

### Rules

1. **Schema-first:** If flow YAML changes, update features in the same change set.
2. **No new steward CLI on the node** — tests continue to use global `gate decide`.
3. **Pair markdown assertions** — if `run_context.feature` gains “markdown contains presentation body”, use fixture with known presentation text from porcelain-0007-v005-present-gate.

## Implementation slices

Execute in order; each slice should keep `@node.shape.present.gate` green.

### Slice 1 — Context artifact resolution (engine)

**Files**

- `.cursor/foundry/cli/foundry_cli/context.py` — extend `_reads_block` or post-process in `assemble_context` to resolve `reads.artifacts` with `from: nearest_sealed_ancestor` for sealed `shape.present` visits (start with `shape.present.presentation` only).
- `.cursor/foundry/cli/foundry_cli/paths.py` or new small module (e.g. `artifact_reads.py`) — helper: given snapshot, flow, run_dir, logical artifact ref → `{ resolved_uri, resolved_path }`.
- Optionally reuse logic from archive / hook code that already locates sealed presentation paths (grep `presentation` + sealed visit).

**Behavior**

- JSON context: artifact entries include `resolved_uri` / `resolved_path` when resolvable.
- Do not break nodes that only declare artifacts without resolution today.

**Tests**

- **Unit:** fixture snapshot with sealed `shape.present` → gate context resolves presentation path.
- **Feature:** extend `shape_present_gate.feature` “Run context” table or add row for resolved artifact fields (if JSON exposes them).

### Slice 2 — Markdown presentation section (render)

**Files**

- `.cursor/foundry/cli/foundry_cli/render.py` — for `shape.present.gate`, add `## Plan presentation` with full file contents when `presentation_artifact_path` or resolved artifact path exists on disk; truncate or warn if huge (document limit if any).
- `.cursor/foundry/cli/foundry_cli/commands.py` — ensure `cmd_run_context` passes resolved paths into render (if read happens at command layer today).

**Tests**

- **Feature:** `run_context.feature` scenario “Steward loads markdown context for shape.present.gate” — assert substring from fixture presentation markdown; keep existing instruction assertions.

### Slice 3 — Instructions + paired gate consistency

**Files**

- `.cursor/foundry/nodes/shape.present.gate/instructions.md` — Turn 1: canonical packet sections; remove path-vs-artifact OR once Slices 1–2 land.
- `.cursor/foundry/nodes/shape.examine.gate/instructions.md` — add `--json` to `gate decide` fences if convention is JSON-first (pair with present gate).

**Tests**

- **Feature:** `run_context.feature` — optional assert `gate decide` fences in markdown include `--json` for both gates if changed.

### Slice 4 — Documentation and rules

| File | Action |
|------|--------|
| `.cursor/foundry/nodes/shape.present.gate/doc.yaml` | Set status aligned with product; update sequence note for two-turn STOP before decide |
| `steward-ux.mdc` / gate instructions | One explicit bullet under present gate: presentation body comes from context packet after cleanup (if not already) |
| `.cursor/rules/node-instructions.mdc` | Add **Shape present gate** row: engine decides/routes; steward two-turn presentation + `gate decide`; no worker |
| `docs/plans/node-inventory.md` | Boundary status: gate / user-decider / context packet |
| Regenerate `.cursor/foundry/catalog/nodes/shape.present.gate.index.yaml`, `docs/nodes/shape.present.gate.md` | After doc.yaml + any schema notes |

### Slice 5 — Optional shared follow-up (document if deferred)

- Use same `nearest_sealed_ancestor` resolver for `shape.record` context and materialization noted in shape.present plan.
- `shape.record.gate` presentation parity audit (out of scope unless trivial reuse).

## Docgen / catalog sync

After flow or doc.yaml changes:

```bash
# Project doc build / catalog sync as documented in repo (e.g. foundry dev doc-build, catalog-build)
```

Verify:

- `catalog/nodes/shape.present.gate.index.yaml` — `checks_used`, connections, test list unchanged unless intentional.
- Generated node page permissions match empty CLI allow and reads table.
- Foundry dev docs under `.cursor/foundry/cli/docs/nodes/shape.present.gate.md` if mirrored from `docs/nodes/`.

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | Opened gate: user `gate decide reject` → next node `shape.examine`, opened lifecycle. |
| AC2 | Opened gate: user `gate decide accept` → next node `shape.record`, opened lifecycle. |
| AC3 | Invalid decision → `INVALID_GATE_DECISION`; `visit transition` → `GATE_USE_DECIDE`. |
| AC4 | Admit without sealed `shape.present` → `prior-present-sealed` halt (existing fixture). |
| AC5 | JSON `run context`: node_id, options, prompt, reads.state keys, artifact declaration; empty `allow.cli`; `allow.user.decide` true. |
| AC6 | Markdown `run context`: two-turn instructions inlined; verbatim-AC rule; **full presentation body** visible without steward reading undeclared paths (after Slices 1–2). |
| AC7 | No worker binding, no new `allow.cli`, no `judgment.md` for this node. |
| AC8 | `shape.examine.gate` fence/`--json` consistency per decision point 3. |
| AC9 | Catalog index and generated node doc reflect post-cleanup authoring status. |

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Resolver wrong visit for ancestor | Unit test with multiple visits; match check expression for `prior-present-sealed` |
| Large presentation.md bloats context | Document size cap or “see path” fallback with warning in render |
| Breaking JSON context artifact shape | Add fields additively (`resolved_path`); keep declaration fields |
| Partial implement leaves dual-source instructions | Ship instructions change in same PR as render/resolver |

## Suggested PR breakdown

1. **PR1 — Resolver + unit tests** (Slice 1).
2. **PR2 — Render section + run_context feature assertions** (Slice 2).
3. **PR3 — Instructions, examine.gate parity, doc.yaml, node-instructions, catalog regen** (Slices 3–4).

Prefer one PR if CI stays green and diff stays reviewable.

## Reference: implementation map (today)

| Concern | Location |
|---------|----------|
| Gate decide | `foundry_cli/engine/gates.py` (`decide_gate`) |
| Seal + route | `foundry_cli/engine/lifecycle.py` (`_seal_visit_and_route`, `GATE_USE_DECIDE`) |
| Gate presented event | `foundry_cli/engine/lifecycle.py` (`gate.presented`) |
| Context packet | `foundry_cli/context.py` (`assemble_context`, `_reads_block`) |
| Markdown render | `foundry_cli/render.py` (`render_context_markdown`) |
| Prior present check | `flows/implementation/registry.yaml` checks + flow.checks `prior-present-sealed` |
| Node assets | `.cursor/foundry/nodes/shape.present.gate/` (`instructions.md`, `doc.yaml`) |
| Acceptance | `tests/acceptance/features/shape_present_gate.feature`, `run_context.feature` |
| Product UX | `.cursor/rules/steward-ux.mdc`, gate `instructions.md` |

## Verification checklist

- [x] Target `shape.present.gate` block in `flows/implementation/registry.yaml` matches this plan (unchanged).
- [x] Presentation content available in markdown context without steward file guesswork.
- [x] `reads.artifacts` resolution implemented (`artifact_reads.py`); steward path OR removed from instructions.
- [x] **Unit:** `test_artifact_reads.py`, `test_render.py` pass.
- [x] **Feature:** `test_shape_present_gate.py`, present-gate `run_context` scenario pass.
- [x] `shape.examine.gate` `gate decide` fences include `--json` (parity with present gate).
- [x] `node-instructions.mdc` gate row added.
- [x] `doc.yaml` status and sequence updated; catalog/docs regen via `catalog build` + `doc build`.
- [x] Acceptance: `@node.shape.present.gate` scenarios green (17 tests in present_gate + run_context).

## Stop condition

Stop after `shape.present.gate` contract cleanup — do not expand into `shape.record` or `shape.record.gate` except shared resolver hooks noted above.
