# Plan: `execute.start` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node review prompt](workflow-node-review-prompt.md), upstream [shape.record.gate contract cleanup](shape.record.gate-contract-cleanup-plan.md) (**done**), [workflow-02-step0-decisions §8](workflow-02-step0-decisions.md), generated [nodes/execute.start.md](../nodes/execute.start.md).

## Goal

`execute.start` is a **user-decider gate with no model worker**: the engine admits the visit, enforces prerequisites, presents the gate prompt, and waits for explicit **Execute authorization** via the operator `start` command (not `gate decide`). The steward performs **presentation-only** chat on turn 1 and proxies `foundry start` on turn 2 after the user authorizes.

| Layer | Owner |
|-------|--------|
| **Judgment** | **User** — explicit authorization to leave Shape and begin Execute on a feature branch |
| **Mechanism** | Engine: `prior-shape-record-sealed`, `approved-ac-recorded`, `gate.presented`, `execute_start_authorization` → `decide_gate(accept)` |
| **Policy** | `foundry start` only at this node with decision wait; `SHAPE_NOT_RECORDED` if record not sealed; no `gate decide` in schema |
| **Presentation** | Steward two-turn UX; `## Living plan` inlined in markdown context |

Happy path:

```
shape.record.gate accept → admit execute.start → on_examine (prior-shape-record-sealed, approved-ac-recorded)
  → on_open / gate.presented
  → Turn 1: steward shows living plan + verbatim approved_ac + authorize via start → STOP
  → Turn 2: user confirms → steward `start` (or user runs CLI on branch) → sealed → execute.intake
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** No worker, no task, no `judgment.md`. Semantic judgment is the **user’s** authorization act, recorded by `execute.authorization.recorded` + gate accept.

## Runtime sequence (Step 1)

1. `shape.record.gate` seals with decision **accept** → connection to `execute.start`.
2. Visit admitted → `on_examine` runs `prior-shape-record-sealed` and `approved-ac-recorded`.
3. `on_open` → lifecycle `opened`; engine emits decision wait (`request_ref: gate:execute.start`).
4. Steward loads `run context --markdown`; instructions from `nodes/execute.start/instructions.md`.
5. **Two-turn UX:** Turn 1 — `## Living plan` + verbatim `approved_ac` + how to authorize; Turn 2 — `start` after explicit user confirmation.
6. `execute_start_authorization` (`operator.py`): append `execute.authorization.recorded`, `decide_gate(accept)`, clear wait, route.
7. Connection **accept** → `execute.intake`.

`operations.yaml`: none. `start` is global operator CLI, not node `allow.cli`.

## Contract (Step 2)

### Inputs

| When gate opens | Source |
|-----------------|--------|
| `approved_ac`, `plan_path` | State from sealed `shape.record` |
| `shape.record.plan` | Sealed ancestor visit artifact (`nearest_sealed_ancestor`) |

### Outputs

| On successful gate close | Output |
|--------------------------|--------|
| Visit sealed, outcome `completed` | Ledger + routing |
| `execute.authorization.recorded` | Evidence of explicit authorization |
| Decision `accept` | Connection to `execute.intake` |

### Consumers

| Consumer | Uses |
|----------|------|
| `execute.intake` | `approved_ac`, `plan_path`, sealed plan artifact; expects authorization event |

## Responsibility table (Step 3 — distilled)

| Responsibility | Correct category | Owner |
|----------------|------------------|-------|
| Prerequisite checks | POLICY | Engine `on_examine` |
| Gate prompt + wait | MECHANISM | Engine |
| Plan body for steward | MECHANISM | Context resolve + `## Living plan` render |
| User authorization | JUDGMENT | User via `foundry start` |
| Two-turn presentation | PRESENTATION | Steward instructions |
| Seal + route | MECHANISM | `execute_start_authorization` + `decide_gate` |

## Minimal schema (Step 9)

```yaml
  - id: execute.start
    kind: gate
    title: Start execute phase
    instructions: registry:nodes/execute.start/instructions.md
    reads:
      state:
      - approved_ac
      - plan_path
      artifacts:
      - artifact: shape.record.plan
        from: nearest_sealed_ancestor
    produces:
      options:
      - accept
    prompt: Frozen plan recorded. Run `foundry start` on this run to authorize Execute and advance to execute.intake on your feature branch.
    lifecycle:
      on_examine:
      - check: prior-shape-record-sealed
      - check: approved-ac-recorded
    decider: user
    allow:
      user:
        decide: true
```

No `allow.cli`, worker, or receipts.

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| No steward instructions | `nodes/execute.start/instructions.md` (two-turn; `start` not `gate decide`) |
| No `reads` / living plan in packet | Flow `reads` + render `## Living plan` for `execute.start` |
| `on_examine` weaker than intake | Add `prior-shape-record-sealed` (align with `execute.intake`) |
| `doc.yaml` / rules missing | Authoring doc + `node-instructions.mdc` row |
| Context tests | `run_context.feature` scenario; `test_render` for execute.start living plan |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_user_cli_execute.py tests/unit/test_render.py -q -k "start or execute_start or living_plan"
pytest tests/acceptance/test_user_cli.py tests/acceptance/test_run_context.py -q -k "start or execute.start or Authorize"
```

Tag: `@node.execute.start` (optional feature file; existing `user_cli` / `execute_slice_*` cover `start`).

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | After record gate accept + advance, active node `execute.start` with decision wait |
| AC2 | `start` records `execute.authorization.recorded` and opens `execute.intake` |
| AC3 | `start` rejected when not at `execute.start` (`EXECUTE_START_GATE_REQUIRED`) |
| AC4 | `on_examine` halts without sealed record + approved AC |
| AC5 | Markdown context: `## Living plan`, instructions, `start` fence with `--json`; empty `allow.cli` |
| AC6 | Prompt has no `/craft-execute` (workflow-02 §8) |
| AC7 | No worker, no `judgment.md`, no `allow.cli` for `gate decide` |

## Deferred

- Regenerate `docs/nodes/execute.start.md` via `doc build` if not run in CI.
- Dedicated `execute_start.feature` with `@node.execute.start` (covered by existing slices).
- Host auto-advance past intake in some test fixtures (`test_user_cli_execute` expects `execute.build` with host).

## Verification checklist

- [x] `flows/implementation/registry.yaml` node block: instructions, reads, `prior-shape-record-sealed`.
- [x] `## Living plan` in markdown context for `execute.start`.
- [x] `nodes/execute.start/instructions.md` + `doc.yaml`.
- [x] Unit tests for render; run_context scenario.
- [x] `node-instructions.mdc` execute.start row.
- [x] Catalog index checks updated.
