# Plan: `shape.record.gate` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node review prompt](workflow-node-review-prompt.md), upstream [shape.record contract cleanup](shape.record-contract-cleanup-plan.md) (**done**), sibling patterns [shape.present.gate](shape-present-gate-contract-cleanup-plan.md), [shape.examine.gate](../nodes/shape.examine.gate.md).

## Goal

`shape.record.gate` is a **user-decider gate with no model worker**: the engine admits the visit, enforces prerequisites, presents options, validates `gate decide`, seals the visit, and routes by decision. The steward performs **presentation-only** chat on turn 1 and proxies the user's **accept** or **hold** on turn 2.

| Layer | Owner |
|-------|--------|
| **Judgment** | **User** — accept frozen plan + approved AC, or hold to reshape via `shape.present` |
| **Mechanism** | Engine: `prior-shape-record-sealed`, `approved-ac-recorded`, `gate.presented`, `decide_gate`, `_seal_visit_and_route` |
| **Policy** | `INVALID_GATE_DECISION`, `GATE_USE_DECIDE`, opened-only decide; hold does not call `gate decide` until user accepts |
| **Presentation** | Steward two-turn UX; `## Living plan` inlined in markdown context |

Happy path:

```
shape.record sealed → admit shape.record.gate → on_examine (prior-shape-record-sealed, approved-ac-recorded)
  → on_open / gate.presented
  → Turn 1: steward shows full living plan + verbatim approved_ac → STOP
  → Turn 2: user accept|hold → gate decide → sealed → execute.start | shape.present (reshape_plan)
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** No worker, no task, no `judgment.md`.

## Runtime sequence (Step 1)

1. `shape.record` seals → connection to `shape.record.gate`.
2. Visit admitted → `on_examine` runs `prior-shape-record-sealed` and `approved-ac-recorded`.
3. `on_open` → lifecycle `opened`; engine emits `gate.presented` with options + flow `prompt`.
4. Steward loads `run context --markdown`; instructions from `nodes/shape.record.gate/instructions.md`.
5. **Two-turn UX:** Turn 1 — `## Living plan` body + verbatim `approved_ac`; Turn 2 — `gate decide --decision accept|hold --json`.
6. `decide_gate` validates options, records decision, `_seal_visit_and_route`.
7. Routing: **accept** → `execute.start`; **hold** → `shape.present` (`loop: reshape_plan`).

## Contract (Step 2)

### Inputs

| When gate opens | Source |
|-----------------|--------|
| `approved_ac`, `approved_ac_digest`, `plan_path`, `plan_version` | State from `shape.record` complete |
| `shape.record.plan` | Sealed ancestor visit artifact (`nearest_sealed_ancestor`) |

### Outputs

| On successful gate close | Output |
|--------------------------|--------|
| Visit sealed, outcome `completed` | Ledger + routing |
| Decision `accept` \| `hold` | Connection selection |

### Consumers

| Consumer | Uses |
|----------|------|
| `execute.start` (accept) | Frozen plan / AC policy for execute phase |
| `shape.present` (hold) | Reshape loop; may read `approved_ac` on re-entry |

## Responsibility table (Step 3 — distilled)

| Responsibility | Correct category | Owner |
|----------------|------------------|-------|
| Prerequisite checks | POLICY | Engine lifecycle |
| Gate options + prompt | MECHANISM | Engine `gate.presented` |
| Plan body for steward | MECHANISM | Context resolve + `## Living plan` render |
| User accept/hold | JUDGMENT | User |
| Two-turn presentation | PRESENTATION | Steward instructions |
| Seal + route | MECHANISM | Engine `gates.py` |

## Minimal schema (Step 9)

Flow entry unchanged — already minimal (`allow.user.decide` only; no `allow.cli`, worker, or receipts).

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| Dual-source plan in instructions | Turn 1 cites `## Living plan` packet section only |
| No inlined plan in markdown context | `render.py` adds `## Living plan` for `shape.record.gate` |
| `plan_path` fallback for artifact resolve | `artifact_reads.py` mirrors `presentation_artifact_path` for `shape.record.plan` |
| Turn 2 hold fence | Instructions include `gate decide --decision hold --json` |
| `doc.yaml` / rules | Status `ok`, two-turn sequence; `node-instructions.mdc` row |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/acceptance/test_shape_record_gate.py tests/acceptance/test_run_context.py -q -k "record_gate or record.gate"
pytest tests/unit/test_artifact_reads.py tests/unit/test_render.py -q -k "record_gate or living_plan or plan_path"
```

Tag: `@node.shape.record.gate`.

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | `gate decide accept` → `execute.start` opened |
| AC2 | `gate decide hold` → `shape.present` opened (`reshape_plan`) |
| AC3 | Invalid decision / `visit transition` policy errors |
| AC4 | `on_examine` halts without sealed record + approved AC |
| AC5 | JSON context: reads, options, empty `allow.cli`, `allow.user.decide` |
| AC6 | Markdown context: `## Living plan` with fixture plan body; two-turn instructions; `--json` fences |
| AC7 | No worker, no new `allow.cli`, no `judgment.md` |

## Deferred

- `workspace:plan.md` inline in gate packet (record step mirrors to workspace; gate uses sealed artifact + `plan_path` only).
- Regenerate `docs/nodes/shape.record.gate.md` if `doc build` not run in CI for this branch.
- Record gate packet documented in steward-ux + gate instructions (optional explicit bullet).

## Verification checklist

- [x] `factory-flow.yaml` node block unchanged (minimal gate).
- [x] `## Living plan` in markdown context with fixture text.
- [x] `reads.artifacts` resolution + `plan_path` fallback.
- [x] Unit tests for render + artifact_reads.
- [x] Feature: `shape_record_gate.feature`, `run_context` record-gate scenario.
- [x] `node-instructions.mdc` record gate row.
- [x] `doc.yaml` status and sequence updated.
