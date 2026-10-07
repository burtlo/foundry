# Plan: `verify.acceptance` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [verify.intake contract cleanup](verify.intake-contract-cleanup-plan.md), author reference [nodes/verify.acceptance/doc.yaml](../../.cursor/foundry/nodes/verify.acceptance/doc.yaml).

## Goal

`verify.acceptance` is a **host-owned deterministic step with no model worker on the happy path**: the engine admits the visit, runs `_assess_acceptance` / `_resolve_acceptance_decision`, publishes `verify-findings`, seals an `implementation-validator`-labeled agent receipt, and transitions. The steward does **not** bind `implementation-validator` or manually publish findings on the default path.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None on happy path** — `gate_decision` is deterministic host assessment |
| **Mechanism** | Engine: `run_verify_acceptance_complete` via `run advance` when visit is `opened` |
| **Policy** | `on_examine` `prior-verify-intake-sealed`; `on_seal` `agent-receipt-sealed` |
| **Presentation** | Steward markdown blurb in `run context` (engine-owned step) |

Happy path:

```
verify.intake.gate pass → admit verify.acceptance → on_examine
  → run advance → verify-findings + agent receipt → transition → verify.acceptance.gate
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** Legacy `implementation-validator` worker remains in catalog docs only; flow binding removed. Future bounded validator evidence is a separate slice (gap closure plan).

## Runtime sequence (Step 1)

1. Incoming: `verify.intake.gate` **pass**.
2. Visit admitted → `on_examine`: `prior-verify-intake-sealed`.
3. Host / `run advance` calls `run_verify_acceptance_complete` when lifecycle is `opened`.
4. Engine resolves branch diff, assesses AC / execute test exit / diff usability.
5. Publishes `verify-findings.json`, patches `verify_findings` state, seals agent receipt.
6. `transition` to `verify.acceptance.gate` (gate maps `gate_decision`).

`operations.yaml`: author-only docgen. Mechanism in `verify_step_executor.py`.

## Contract (Step 2)

### Inputs

| When step opens | Source |
|-----------------|--------|
| `approved_ac`, `final_commit_sha`, `last_test_exit_code`, `branch_diff_artifact_path` | Run state |
| `shape.record.plan`, `verify.intake.branch-diff` | `nearest_sealed_ancestor` artifacts |

### Outputs

| On complete | Output |
|-------------|--------|
| Sealed visit, outcome `completed` | Route to `verify.acceptance.gate` |
| `verify.acceptance.verify-findings` | Downstream verify steps + gate routing |
| Agent receipt (`implementation-validator`, validate mode) | `on_seal` check |

### Consumers

| Consumer | Uses |
|----------|------|
| `verify.acceptance.gate` | `gate_decision`, `evidence_ok` in findings |
| `verify.code_review`+ | `verify.acceptance.verify-findings` |

## Minimal schema (Step 9)

See `flows/implementation/registry.yaml` — no `instructions`, `worker`, steward `allow.cli`, or `files.write`.

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| Worker bound on host-owned step | Remove `worker` from flow + catalog index |
| Legacy `registry:steps/verify-acceptance.md` | Drop flow reference; author `nodes/verify.acceptance/{doc,operations}.yaml` |
| Steward context | `render.py` engine-owned blurb for `verify.acceptance` |
| Context packet schema | Exempt `verify.acceptance` from required `instructions` |
| node-instructions.mdc | Verify acceptance ownership table |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_verify_evidence.py tests/unit/test_workflow_slices_2c_2f.py -q
pytest tests/unit/test_render.py tests/unit/test_verify_acceptance_context.py -q
pytest tests/unit/test_registry_refs.py -q
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | After verify intake gate pass, `run advance` seals verify.acceptance and reaches acceptance gate |
| AC2 | Flow has no worker binding for `verify.acceptance` |
| AC3 | `run context` markdown describes host-owned verify acceptance (no worker table in generated node doc) |
| AC4 | Context packet validates without `instructions` for opened `verify.acceptance` |
| AC5 | Registry ref tests no longer require `verify-acceptance.md` in flow |

## Verification checklist

- [x] `flows/implementation/registry.yaml` node block: no worker/instructions; engine-owned allow.
- [x] `nodes/verify.acceptance/doc.yaml` + `operations.yaml`.
- [x] Catalog index + `node-instructions.mdc`.
- [x] `render.py` steward blurb.
- [x] Unit tests.
