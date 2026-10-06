# Plan: `verify.code_review.gate` contract cleanup

Status: **done** (implementer slice; uncommitted).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [verify.code_review contract cleanup](verify.code_review-contract-cleanup-plan.md).

## Goal

`verify.code_review.gate` is a **user decider gate** with no worker: steward two-turn UX (presentation → `gate decide`); engine seals and routes **accept** / **reject** / **reshape**. Review content comes from the sealed `verify.code_review` step (`verify-notes.md`, `verify_notes` state) — not re-summarized from ad hoc reads.

| Layer | Owner |
|-------|--------|
| **Judgment** | User only |
| **Mechanism** | `gate decide` with `produces.options` |
| **Policy** | `on_examine` `prior-verify-acceptance-sealed`; steward-ux two-turn minimum |
| **Presentation** | Inlined `## Verify notes` in markdown context; verbatim `approved_ac` from `reads.state` |

## Runtime sequence

1. Incoming: sealed `verify.code_review` with `verify-notes` artifact and `verify_notes` state patch.
2. Visit admitted → user gate opened; steward Turn 1 from packet; Turn 2 `gate decide`.
3. Engine seals visit and routes per decision.

## Contract

### Inputs (`reads`)

| Kind | Paths |
|------|--------|
| State | `approved_ac`, `verify_notes`, `verify_findings`, `feature_branch` |
| Artifacts | `verify.code_review.verify-notes`, `verify.intake.branch-diff`, `verify.acceptance.verify-findings` (`nearest_sealed_ancestor`) |

### Outputs

| On `gate decide` | Route |
|------------------|--------|
| `accept` | `verify.complete` |
| `reject` | `execute.repair.limit.gate` |
| `reshape` | `shape.intake` (loop `reshape`) |

## Gaps addressed

| Area | Fix |
|------|-----|
| Steward summarized `reads` in Turn 1 | Point at inlined `## Verify notes`; verbatim `approved_ac` |
| Gate had no `reads` in flow | Add display-only `reads` for context resolution |
| `render.py` | Append `## Verify notes` body for `verify.code_review.gate` |
| `node-instructions.mdc` | Verify code review gate ownership row |
| `workflow-node-revision-patterns.md` | Presentation row for user gate |

## Instruction audit (`instructions.md`)

| Section | Action |
|---------|--------|
| Goal, two-turn, STOP, Turn 2 fences, boundaries | **KEEP** |
| Turn 1 “summarize findings / branch diff” | **REPLACE** — full packet from `## Verify notes`; verbatim `approved_ac` |

Target ≤ 80 lines; no duplicate file loading.

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_render.py -q -k "code_review_gate"
pytest tests/unit/test_registry_refs.py -q
```

### Schema oracle

| Element | Prove |
|---------|--------|
| `decider: user`, `allow.user.decide` | `gate decide` for accept/reject/reshape |
| `reads.artifacts` | Resolved URI/path in JSON context when fixture present |
| Markdown | `## Verify notes` body + inlined `## Instructions` (two-turn) |

Tag: `@node.verify.code_review.gate` (optional acceptance feature later).

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | Turn 1 instructions cite packet `## Verify notes`, not steward summarization |
| AC2 | Flow `reads` declare verify-notes + supporting artifacts |
| AC3 | `run context` markdown includes verify-notes body when resolved path exists |
| AC4 | Unit render test for code review gate |
