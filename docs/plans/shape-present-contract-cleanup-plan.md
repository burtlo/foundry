# Plan: `shape.present` contract cleanup

Status: **done** (slices 1–7; host multi-agent advance fix in `run_service.py`)

Related: [workflow node review prompt](workflow-node-review-prompt.md), completed [shape-examine-contract-cleanup-plan](shape-examine-contract-cleanup-plan.md), generated [nodes/shape.present.md](../nodes/shape.present.md).

## Goal

`shape.present` is a **judgment-bounded step with an engine-owned completion path** (mirror `shape.examine`):

The model (shape-presenter / structured task) proposes succinct presentation markdown and `presented_ac`, with an explicit PROCEED vs BLOCKED verdict. Foundry validates, writes `presentation.md`, patches state, seals the agent receipt, and transitions to `shape.present.gate`.

| Layer | Owner |
|-------|--------|
| **Judgment** | Model: synthesize user-facing plan presentation from examination state |
| **Mechanism** | Engine: extract presentation from accepted result, publish artifact, patch state, seal receipt, transition |
| **Policy** | `prior-examine-sealed`, declared-artifact completeness on close, `agent-receipt-sealed` on seal; BLOCKED → no publish/transition |
| **Presentation** | `shape.present.gate` two-turn UX — not steward receipt orchestration prose |

Happy path:

```
enter shape.present → agent wait (presentation judgment) → run agent submit (result)
  → visit present complete (or run advance) → seal + transition → shape.present.gate
```

**Testing principle:** Unit tests prove engine completion; `@node.shape.present` acceptance proves CLI + snapshot + ledger against the **target** schema. Remove scenarios that certify the legacy manual `ledger show` → `state_patch` → write files → `receipt seal` → `transition` chain as the product contract.

## Non-goals

- Redesigning `shape.present.gate`, `shape.record`, or examination nodes.
- Generic `operations.yaml` executor for all nodes.
- Materializing `reads.artifacts` `nearest_sealed_ancestor` in the context packet (document gap; optional follow-up).
- Replacing judgment with the current host-only template in `run_shape_present_complete` (`_presentation_markdown` from `draft_ac` only) as the long-term product path — that path may remain as **test/host fallback** only if explicitly documented and gated; prefer agent result when present.

## Investigation summary (current vs intended)

### Runtime today (dual path)

1. **Steward path** (`instructions.md`): launch Cursor subagent `shape-presenter` → write `assessment.md` + `agent.json` → `visit state patch` → `artifact publish` → `receipt seal` → `visit transition`.
2. **Host path** (`advance.py` + `run_shape_present_complete`): **no agent wait** (`HOST_OWNED_SHAPE_STEP_NODES` returns `None` from wait setup); advance **deterministically** builds presentation from `draft_ac`/`assumptions`, patches state, publishes, seals stub agent receipt (`mode: engine`), transitions — **never runs shape-presenter**.

These contradict each other and contradict `doc.yaml` / generated docs (steward + worker sequence).

### Schema / contract gaps

| Area | Problem |
|------|---------|
| **Dual completion** | Production `run advance` bypasses judgment; acceptance tests encode manual steward CLI chain. |
| **`allow.cli`** | `ledger.show`, `receipt.link`, `transition`, `visit.state_patch`, `artifact.publish` — duplicates engine completion; `ledger.show` violates node-instructions rule for agent-receipt steps. |
| **`allow.files.write`** | Steward may write `agent.json`, `assessment.md`, `presentation.md` though engine should own publish/receipt on complete. |
| **`reads.state`** | `questions_asked_total` declared but **not consumed** by presenter inputs or engine (dead surface; remove unless implemented). |
| **No agent task** | Only `tasks/shape.examine.yaml` exists; `shape.present` has `worker:` in flow but no `tasks/shape.present.yaml` or `run agent submit` wiring. |
| **`HOST_OWNED_SHAPE_STEP_NODES`** | Treats `shape.present` like deterministic host step — blocks agent wait and forces template completion on advance. |
| **`worker` binding** | `registry:agents/shape-presenter.md` + `contract.yaml` with **wrong** `valid_next_states` (`shape.record`, `shape.examine` vs actual `shape.present.gate`). |
| **Instructions file** | Legacy `instructions.md` (orchestration-heavy) vs target `judgment.md` + minimal steward section in render packet. |
| **No `visit present complete`** | Unlike intake/examine, no semantic CLI for seal + transition after judgment. |
| **Steward UX docs** | Documents examine complete; **silent** on `shape.present` handoff. |
| **`render.py`** | Special section for `shape.examine` only — add parallel **Presentation** section for `shape.present`. |
| **Doc sequence** | `doc.yaml` sequence still shows `ledger show` — remove when steward path narrows. |

### What consumers need

- **`shape.present.gate`**: `presented_ac`, `presentation_artifact_path`, artifact `shape.present.presentation` (nearest sealed).
- **`shape.record`**: reads presentation via nearest sealed ancestor.
- **`run_archive`**: `shape.present.presentation` path.

Successful `shape.present` must leave: sealed visit, `presentation` artifact linked, `presented_ac` + `presentation_artifact_path` in state, agent receipt with PROCEED evidence.

### Agent necessity (Step 6 answer)

**B — Deterministic node with one bounded judgment operation.**

Judgment question: *Given ticket, draft AC, assumptions, examination decisions, and clarifying Q&A, produce succinct user-facing presentation markdown and `presented_ac`, or BLOCKED with blockers.*

Everything else is engine.

## Target contract

### Flow node (`factory-flow.yaml`)

Illustrative target (field order may match catalog):

```yaml
- id: shape.present
  kind: step
  title: Shape present — succinct plan and AC presentation
  produces:
    artifacts:
      - id: presentation
        kind: document
        uri: run:artifacts/{visit_id}/presentation.md
        media_type: text/markdown
  instructions: registry:nodes/shape.present/judgment.md
  reads:
    state:
      - draft_ac
      - assumptions
      - ticket
      - examination_decisions
      - clarifying_questions
      - examination_round
      - approved_ac   # reshape_plan re-entry from shape.record.gate hold
  allow:
    cli:
      - run.agent.submit
      - visit.present.complete
  receipts: registry:schemas/agent-receipt.schema.json
  lifecycle:
    on_examine:
      - check: prior-examine-sealed
    on_seal:
      - check: agent-receipt-sealed
        on_fail:
          action: reopen
          reason: Presentation receipt missing
```

**Remove from node entry:**

- `worker:` block on flow YAML (task registry owns binding; keep agent markdown as task `instructions` ref if needed).
- `allow.cli`: `ledger.show`, `receipt.link`, `transition`, `visit.state_patch`, `artifact.publish`.
- `allow.files.write` for steward draft paths (engine writes on complete).
- `allow.state` for `presented_ac`, `presentation_artifact_path` (engine patches on complete).
- `reads.state.questions_asked_total`.

**Keep:**

- `produces.presentation`, `prior-examine-sealed`, `agent-receipt-sealed`, agent-receipt schema.

### Judgment file

Create `.cursor/foundry/nodes/shape.present/judgment.md` (~25–40 lines):

- Purpose: propose presentation markdown + `presented_ac`.
- Structured output only (no CLI, no routing).
- Reference output schema (new): `registry:schemas/shape-presentation-result.schema.json`.
- PROCEED vs BLOCKED semantics aligned with current shape-presenter assessment sections (migrate essential content from `.cursor/agents/shape-presenter.md` into schema + judgment; agent file can remain as author reference or thin wrapper).

Delete or archive `instructions.md` after migration (flow points to `judgment.md`).

### Task registry

Add `.cursor/foundry/tasks/shape.present.yaml`:

- `node_id: shape.present`
- `instructions: registry:nodes/shape.present/judgment.md`
- `output_schema: registry:schemas/shape-presentation-result.schema.json`
- Input builder: `build_shape_present_input(snapshot, ...)` with fields matching current worker table (`draft_ac`, `assumptions`, `ticket`, `examination_decisions`, `clarifying_questions`, optional `approved_ac` on reshape).

### Output schema

Add `shape-presentation-result.schema.json` with at minimum:

- `presentation_markdown` (string) — body for `presentation.md`
- `presented_ac` (string)
- `verdict` (`PROCEED` | `BLOCKED`)
- `blockers` (string[], required when BLOCKED)
- `summary` (string, short)

### Engine

1. **`apply_presentation_result`** (in `submit.py` or sibling): validate schema; on PROCEED stash accepted result on agent request map; on BLOCKED set wait/block state without completing (mirror examination BLOCKED handling if any — or leave visit opened with sealed receipt only per current blocked acceptance scenario).

2. **`run_shape_present_complete`**: refactor to:
   - Require accepted `shape.present` agent result for steward/complete path.
   - Write `presentation.md` from `presentation_markdown` in result (not `_presentation_markdown` template).
   - Patch `presented_ac`, `presentation_artifact_path`.
   - Build agent receipt from result (not hard-coded PROCEED host string).
   - `transition_visit` to gate.
   - **Advance policy:** When visit opened and accepted PROCEED result exists, call complete (like examine). When no result, set `agent` wait via `ensure_shape_present_request` (new), **remove** `shape.present` from `HOST_OWNED_SHAPE_STEP_NODES` OR split: remove from host-owned set and add task wait emission.

3. **Blocked path:** Receipt seal without publish/transition — either steward-only via explicit CLI or engine command `visit present complete` with `--blocked` / infer from verdict in accepted result. Prefer: **submit with BLOCKED** seals receipt via engine on submit; visit stays opened; acceptance scenario "blocked path" updated to `run agent submit` + no complete.

4. **CLI:** Add `visit present complete` + `CAP_VISIT_PRESENT_COMPLETE`; wire in `commands.py`, capability checks, docgen, node view table.

5. **Remove** `ledger.show` from present capabilities everywhere.

### Tests

| Slice | Work |
|-------|------|
| Unit | `test_shape_present_complete.py` (new): WRONG_NODE, JUDGMENT_MISSING, PROCEED publishes + transitions, BLOCKED codes, receipt `recommended_next_state` = `shape.present.gate` |
| Unit | Update `test_advance.py` / host integration: advance on present **waits for agent** until submit, then completes |
| Acceptance | Rewrite `shape_present.feature` happy path: fixture → agent submit (mock result) → `visit present complete` → gate |
| Acceptance | Blocked: submit BLOCKED → visit still opened; no artifact publish |
| Acceptance | `run_context.feature`: allow cli `run.agent.submit`, `visit.present.complete`; markdown contains `## Judgment` not orchestration fences |
| Acceptance | Remove or narrow scenarios that only test legacy manual chain as contract |
| Keep | Policy scenarios: transition without presentation → `ARTIFACT_INCOMPLETE`; without receipt → reopen; `prior-examine-sealed` halt; gate decide denied |

### Docs / product

- Update `.cursor/foundry/nodes/shape.present/doc.yaml` (ownership: steward minimal; engine complete; remove ledger from sequence).
- Steward UX / node-instructions: paragraph for `shape.present` (mirror examine).
- `render.py`: `## Presentation` blurb for `shape.present`.
- Fix `workers/shape-presenter/contract.yaml` `valid_next_states` → `shape.present.gate` or remove if unused.
- Run doc build / catalog index sync if repo script requires (`catalog-build`, `doc-build`).
- Add `docs/cli/visit-present-complete.md` via docgen.

### `node-instructions.mdc` / rules

Add shape.present row to the engine-owned table **only if** choosing full engine complete with zero steward CLI — **preferred**: judgment + `visit present complete` row (like examine), not full engine-owned like intake.

## Implementation slices (order)

1. **Schema + flow YAML** — target `allow`/`reads`; `judgment.md`; remove dead fields.
2. **Task + JSON schema + input builder + agent wait** — remove present from `HOST_OWNED_SHAPE_STEP_NODES`; emit agent wait on advance.
3. **`run agent submit` + `apply_presentation_result`** for task id `shape.present`.
4. **`visit present complete` + refactor `run_shape_present_complete`**.
5. **Tests** — unit then acceptance; fix host integration expectations.
6. **steward-ux, render, doc.yaml, docgen, catalog index**.
7. **Velma verification** — separate agent.

## Decision points (record in PR)

1. **Blocked handling:** Seal receipt on submit for BLOCKED without `visit present complete` (match current acceptance intent).
2. **Host template fallback:** Delete `_presentation_markdown` from production complete path vs keep only for fixtures without agent infrastructure — **recommend delete** from complete; tests use submit.
3. **Cursor subagent `shape-presenter.md`:** Keep for Task tool launches in IDE; registry task is source of truth for host `run agent submit`.
4. **`approved_ac` on reshape:** Include in `reads.state` and task input when `shape.record.gate` hold loops to present.

## Verification checklist (Velma)

- [ ] `factory-flow.yaml` `shape.present` matches target contract.
- [ ] No `ledger.show` on present node.
- [ ] `HOST_OWNED_SHAPE_STEP_NODES` does not skip agent wait for present (unless documented exception).
- [ ] `visit present complete` documented and capability-gated.
- [ ] `@node.shape.present` and `run_context` scenarios pass.
- [ ] `job_host.feature` / host integration still reach `shape.present.gate` after agent path.
- [ ] Generated `docs/nodes/shape.present.md` reflects new ownership (after doc build).
- [ ] Steward docs document present handoff.

## Stop condition

Stop after `shape.present` — do not refactor `shape.record` in this plan (sibling node; note coupling only).
