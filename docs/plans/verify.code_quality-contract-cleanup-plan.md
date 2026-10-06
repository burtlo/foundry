# Plan: `verify.code_quality` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [verify.acceptance contract cleanup](verify.acceptance-contract-cleanup-plan.md), author reference [nodes/verify.code_quality/doc.yaml](../../.cursor/foundry/nodes/verify.code_quality/doc.yaml).

## Goal

`verify.code_quality` is a **host-owned deterministic step with no model worker on the happy path**: the engine admits the visit, runs manifest or stub lint/code_quality commands via `run_verify_code_quality_complete`, publishes `code-quality-report`, seals an `implementation-validator`-labeled agent receipt, and transitions (or seals `not_applicable` when review is disabled). The steward does **not** bind workers or manually publish the report on the default path.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None on happy path** — pass/repair is receipt command exit codes at `verify.code_quality.gate` |
| **Mechanism** | Engine: `run_verify_code_quality_complete` via `run advance` when visit is `opened` (or `examined` after skip examine) |
| **Policy** | `on_examine` `prior-verify-acceptance-sealed`, `review-enabled` (skip → `not_applicable`); `on_seal` `agent-receipt-sealed` when completed |
| **Presentation** | Steward markdown blurb in `run context` (engine-owned step) |

Happy path (review enabled):

```
verify.acceptance.gate pass → admit verify.code_quality → on_examine
  → run advance → code-quality-report + agent receipt → transition → verify.code_quality.gate
```

Skip path (review disabled):

```
verify.acceptance.gate pass → admit verify.code_quality → review-enabled fails
  → run advance → not_applicable → verify.code_review
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** Bugbot / security-review subagents are future bounded evidence (gap closure plan).

## Runtime sequence (Step 1)

1. Incoming: `verify.acceptance.gate` **pass**.
2. Visit admitted → `on_examine`: `prior-verify-acceptance-sealed`, `review-enabled`.
3. Host / `run advance` calls `run_verify_code_quality_complete` when lifecycle is `opened` or `examined`.
4. If review disabled: seal `not_applicable`, route to `verify.code_review`.
5. Else: run commands, publish report, seal agent receipt, transition to `verify.code_quality.gate`.

`operations.yaml`: author-only docgen. Mechanism in `verify_step_executor.py`.

## Contract (Step 2)

### Inputs

| When step opens | Source |
|-----------------|--------|
| `feature_branch`, `verify_findings` | Run state |
| `config.review`, `config.verification` | App manifest |
| `verify.intake.branch-diff` | `nearest_sealed_ancestor` artifact |

### Outputs

| On complete | Output |
|-------------|--------|
| Sealed visit, outcome `completed` | Route to `verify.code_quality.gate` |
| Sealed visit, outcome `not_applicable` | Route to `verify.code_review` (review disabled) |
| `verify.code_quality.code-quality-report` | Steward / gate evidence |
| Agent receipt (`implementation-validator`, validate mode) | `on_seal` check when completed |

### Consumers

| Consumer | Uses |
|----------|------|
| `verify.code_quality.gate` | Agent receipt command exit codes |
| `verify.code_review` | `code-quality-done-or-skipped` check |

## Minimal schema (Step 9)

See `factory-flow.yaml` — no `instructions`, `worker`, steward `allow.cli`, or `files.write`.

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| Steward step instructions on host-owned step | Remove `instructions` from flow + catalog index |
| Legacy `registry:steps/verify-code-quality.md` | Drop flow reference; author `nodes/verify.code_quality/{doc,operations}.yaml` |
| Steward context | `render.py` engine-owned blurb for `verify.code_quality` |
| Context packet schema | Exempt `verify.code_quality` from required `instructions` |
| `ENGINE_OWNED_STEP_NODE_IDS` | Include `verify.code_quality` |
| node-instructions.mdc | Verify code quality ownership table |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_verify_evidence.py tests/unit/test_workflow_slices_2c_2f.py -q
pytest tests/unit/test_render.py tests/unit/test_verify_code_quality_context.py -q
pytest tests/unit/test_registry_refs.py -q
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | After acceptance gate pass with review enabled, `run advance` seals verify.code_quality and reaches code quality gate |
| AC2 | With review disabled, `run advance` seals `not_applicable` and routes toward code review |
| AC3 | Flow has no `instructions` or steward publish grants for `verify.code_quality` |
| AC4 | `run context` markdown describes host-owned verify code quality (no Instructions section) |
| AC5 | Context packet validates without `instructions` for opened `verify.code_quality` |
| AC6 | Registry ref tests no longer require `verify-code-quality.md` in flow |

## Verification checklist

- [x] `factory-flow.yaml` node block: no instructions/steward allow; engine-owned allow via default transition.
- [x] `nodes/verify.code_quality/doc.yaml` + `operations.yaml`.
- [x] Catalog index + `node-instructions.mdc`.
- [x] `render.py` steward blurb.
- [x] Unit tests.
