# Plan: `verify.code_review` contract cleanup

Status: **done** (implementer slice; uncommitted).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [verify.code_quality contract cleanup](verify.code_quality-contract-cleanup-plan.md), author reference [nodes/verify.code_review/doc.yaml](../../.cursor/foundry/nodes/verify.code_review/doc.yaml).

## Goal

`verify.code_review` is a **host-owned deterministic step with no model worker on the happy path**: the engine admits the visit after acceptance and code-quality preconditions, runs `run_verify_code_review_complete` via `run advance` when the visit is `opened`, publishes `verify-notes.md`, patches `verify_notes` state for the user gate, and transitions to `verify.code_review.gate`. Human accept / reject / reshape stays at the **user gate** only.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None on this step** — human decision is `verify.code_review.gate` only |
| **Mechanism** | Engine: `run_verify_code_review_complete` via `run advance` when visit is `opened` |
| **Policy** | `on_examine` `acceptance-passed`, `code-quality-done-or-skipped` |
| **Presentation** | Steward markdown blurb in `run context` (engine-owned step) |

Happy path:

```
verify.code_quality.gate pass (or code_quality skipped) → admit verify.code_review → on_examine
  → run advance → verify-notes.md + verify_notes state → transition → verify.code_review.gate
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** No Bugbot or review subagent on this step.

## Runtime sequence (Step 1)

1. Incoming: sealed `verify.code_quality.gate` **pass** or `verify.code_quality` **not_applicable**.
2. Visit admitted → `on_examine`: `acceptance-passed`, `code-quality-done-or-skipped`.
3. Host / `run advance` calls `run_verify_code_review_complete` when lifecycle is `opened`.
4. Publish `verify-notes`, patch allowed state, transition to `verify.code_review.gate`.

`operations.yaml`: author-only docgen. Mechanism already in `verify_step_executor.py` and `advance.py`.

## Contract (Step 2)

### Inputs

| When step opens | Source |
|-----------------|--------|
| `approved_ac`, `verify_findings`, `branch_diff_artifact_path` | Run state |
| `verify.intake.branch-diff`, `verify.acceptance.verify-findings` | `nearest_sealed_ancestor` artifacts |

### Outputs

| On complete | Output |
|-------------|--------|
| Sealed visit, outcome `completed` | Route to `verify.code_review.gate` |
| `verify.code_review.verify-notes` | User gate presentation / steward reads |
| `verify_notes` (state patch) | Gate context |

### Consumers

| Consumer | Uses |
|----------|------|
| `verify.code_review.gate` | User gate instructions + `verify_notes` / artifacts |
| `verify.complete` | Indirect via gate **accept** |

## Minimal schema (Step 9)

Mirror `verify.code_quality`: no flow `instructions`, no steward `allow.cli` / `allow.files.write` / broad `allow.state` on the step; keep `reads` for artifact resolution.

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| Steward step instructions on host-owned step | Remove `instructions` from flow + catalog index |
| Legacy `registry:steps/verify-code-review.md` | Drop flow reference; author `nodes/verify.code_review/{doc,operations}.yaml` |
| Steward context | `render.py` engine-owned blurb for `verify.code_review` |
| Context packet schema | Exempt `verify.code_review` from required `instructions` |
| `ENGINE_OWNED_STEP_NODE_IDS` | Include `verify.code_review` |
| node-instructions.mdc | Verify code review ownership table |
| workflow-node-revision-patterns.md | `## Verify code review` presentation row |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_verify_evidence.py -q -k code_review
pytest tests/unit/test_render.py tests/unit/test_verify_code_review_context.py -q
pytest tests/unit/test_registry_refs.py -q
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | After code quality gate pass (or skip), `run advance` seals verify.code_review and reaches code review gate |
| AC2 | Flow has no `instructions` or steward publish grants for `verify.code_review` |
| AC3 | `run context` markdown describes host-owned verify code review (no Instructions section) |
| AC4 | Context packet validates without `instructions` for opened `verify.code_review` |
| AC5 | Registry ref tests no longer require `verify-code-review.md` in flow |

## Verification checklist

- [x] `flows/implementation/registry.yaml` node block: no instructions/steward allow; engine-owned allow via default transition.
- [x] `nodes/verify.code_review/doc.yaml` + `operations.yaml`.
- [x] Catalog index + `node-instructions.mdc`.
- [x] `render.py` steward blurb.
- [x] Unit tests (`_apply_engine_state` for `verify_notes` — no steward `allow.state`).
