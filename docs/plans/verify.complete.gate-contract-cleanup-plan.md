# Plan: `verify.complete.gate` contract cleanup

Status: **done** (implementer slice; uncommitted).

Related: [verify.complete contract cleanup](verify.complete-contract-cleanup-plan.md), [verify.code_review.gate contract cleanup](verify.code_review.gate-contract-cleanup-plan.md).

## Goal

`verify.complete.gate` is the **final user decider** after `verify.complete` patches `verified_at`: steward **two-turn** UX (handoff presentation → `gate decide` **accept** only). No verify artifacts on this gate — review content stays at `verify.code_review.gate`.

| Layer | Owner |
|-------|--------|
| **Judgment** | User **accept** only |
| **Mechanism** | `gate decide` with `produces.options: [accept]` |
| **Policy** | Admission after sealed `verify.complete` (connection routing) |
| **Presentation** | `reads.state` handoff fields in markdown `### State` |

## Runtime sequence

1. Incoming: sealed `verify.complete` with `verified_at` in run state.
2. Visit admitted → user gate opened; steward Turn 1 from packet state; Turn 2 `gate decide accept`.
3. Engine seals visit and routes to `deliver.stub` (terminal seal via `run advance` there).

## Contract

### Inputs (`reads`)

| Kind | Paths |
|------|--------|
| State (display only) | `verified_at`, `feature_branch`, `final_commit_sha` |

No `reads.artifacts`.

### Outputs

| On `gate decide` | Route |
|------------------|--------|
| `accept` | `deliver.stub` |

## Instruction audit (`instructions.md`)

| Section | Action |
|---------|--------|
| Goal, two-turn, STOP, Turn 2 fence, boundaries | **KEEP** (slimmed) |
| Turn 1 vague “code review passed” summary | **REPLACE** — handoff from packet `### State`; forbid re-opening verify artifacts |

Target ≤ 50 lines.

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_render.py -q -k "verify_complete_gate"
pytest tests/unit/test_verify_complete_gate_context.py -q
pytest tests/unit/test_registry_refs.py -q
```

### Schema oracle

| Element | Prove |
|---------|--------|
| `decider: user`, `allow.user.decide` | `gate decide` for **accept** |
| `reads.state` keys | Only handoff trio in JSON context |
| Markdown | `### State` with values; `## Instructions` (two-turn); no `## Verify notes` |

Optional later: acceptance feature `@node.verify.complete.gate` (host path + manual gate decide).

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | Turn 1 cites packet `### State`, not ad hoc summarization or artifact reload |
| AC2 | Flow `reads.state` lists only `verified_at`, `feature_branch`, `final_commit_sha` |
| AC3 | `assemble_context` for opened gate exposes minimal state reads |
| AC4 | Unit render + context tests pass |

## Verification checklist

- [x] `flows/implementation/registry.yaml` gate block: minimal `reads.state`; keep `produces.options: [accept]`.
- [x] `nodes/verify.complete.gate/instructions.md` slim two-turn.
- [x] `node-instructions.mdc` Verify complete gate row.
- [x] Unit tests for gate context + render.
