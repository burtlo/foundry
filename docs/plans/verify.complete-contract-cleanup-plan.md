# Plan: `verify.complete` contract cleanup

Status: **done** (implementer slice; uncommitted).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [verify.code_review.gate contract cleanup](verify.code_review.gate-contract-cleanup-plan.md), pattern [verify.code_review contract cleanup](verify.code_review-contract-cleanup-plan.md).

## Goal

`verify.complete` is a **host-owned deterministic step with no model worker on the happy path**: the engine admits the visit after code review gate **accept**, runs `run_verify_complete_complete` via `run advance` when the visit is `opened`, patches `verified_at`, and transitions to `verify.complete.gate`. Final user accept to deliver stays at the **user gate** only.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None on this step** — user accept to deliver is `verify.complete.gate` only |
| **Mechanism** | Engine: `run_verify_complete_complete` via `run advance` when visit is `opened` |
| **Policy** | `on_examine` `code-review-approved` |
| **Presentation** | Steward markdown blurb in `run context` (engine-owned step) |

Happy path:

```
verify.code_review.gate accept → admit verify.complete → on_examine
  → run advance → verified_at state → transition → verify.complete.gate
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.**

## Runtime sequence (Step 1)

1. Incoming: sealed `verify.code_review.gate` with decision **accept**.
2. Visit admitted → `on_examine`: `code-review-approved`.
3. Host / `run advance` calls `run_verify_complete_complete` when lifecycle is `opened`.
4. Patch `verified_at` (allowed state), transition to `verify.complete.gate`.

`operations.yaml`: author-only docgen. Mechanism in `verify_step_executor.py` and `advance.py`.

## Contract (Step 2)

### Inputs

| When step opens | Source |
|-----------------|--------|
| Code review gate accept | Ledger `gate.resolved` on `verify.code_review.gate` |
| `feature_branch`, `final_commit_sha` | Run state (carried; optional context for stewards) |

### Outputs

| On complete | Output |
|-------------|--------|
| Sealed visit, outcome `completed` | Route to `verify.complete.gate` |
| `verified_at` (state patch) | Downstream deliver / handoff semantics |

### Consumers

| Consumer | Uses |
|----------|------|
| `verify.complete.gate` | User accept to `deliver.stub` |
| Operators | `verified_at` timestamp in run state |

## Minimal schema (Step 9)

```yaml
  - id: verify.complete
    kind: step
    title: Verify phase complete
    produces:
      artifacts: []
    allow:
      state:
      - verified_at
    lifecycle:
      on_examine:
      - check: code-review-approved
```

No flow `instructions`, no steward `allow.cli` / `allow.files.write`.

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| Steward step instructions on host-owned step | Remove `instructions` from flow + catalog index |
| Legacy `registry:steps/verify-complete.md` | Drop flow reference; author `nodes/verify.complete/{doc,operations}.yaml` |
| Steward context | `render.py` engine-owned blurb for `verify.complete` |
| Context packet schema | Exempt `verify.complete` from required `instructions` |
| `ENGINE_OWNED_STEP_NODE_IDS` | Include `verify.complete` |
| node-instructions.mdc | Verify complete ownership table |
| workflow-node-revision-patterns.md | `## Verify phase complete` presentation row |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_verify_evidence.py -q -k verify_complete
pytest tests/unit/test_render.py tests/unit/test_verify_complete_context.py -q
pytest tests/unit/test_registry_refs.py -q
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | After code review gate accept, `run advance` seals verify.complete and reaches verify.complete.gate |
| AC2 | Flow has no `instructions` or steward publish grants for `verify.complete` |
| AC3 | `run context` markdown describes host-owned verify phase complete (no Instructions section) |
| AC4 | Context packet validates without `instructions` for opened `verify.complete` |
| AC5 | Registry ref tests no longer require `verify-complete.md` in flow |

## Verification checklist

- [x] `flows/implementation/registry.yaml` node block: no instructions; keep `allow.state` for `verified_at` engine patch.
- [x] `nodes/verify.complete/doc.yaml` + `operations.yaml`.
- [x] Catalog index + `node-instructions.mdc`.
- [x] `render.py` steward blurb.
- [x] Unit tests for complete executor + context + render.
