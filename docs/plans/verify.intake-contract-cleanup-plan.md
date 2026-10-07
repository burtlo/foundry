# Plan: `verify.intake` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [execute.commit.gate contract cleanup](execute.commit.gate-contract-cleanup-plan.md), pattern [execute.intake contract cleanup](execute.intake-contract-cleanup-plan.md), generated [nodes/verify.intake.md](../nodes/verify.intake.md).

## Goal

`verify.intake` is a **host-owned deterministic step with no model worker on the happy path**: the engine admits the visit, enforces execute-commit prerequisites, validates branch diff and commit context, writes assessment + receipts, and transitions on pass. The steward does **not** orchestrate receipt mechanics or invoke `intake-checker.verify` on the default path.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None on happy path** — pass/blocked is deterministic validation |
| **Mechanism** | Engine: `run_verify_intake_complete` via `run advance` when visit is `opened` |
| **Policy** | `on_examine` commit sealed + branch; `on_open` manifest + `validate-verify-context`; blocked intake cannot transition |
| **Presentation** | Steward markdown blurb in `run context` (engine-owned step); blocked summary from receipts |

Happy path:

```
execute.commit.gate pass → admit verify.intake → on_examine + on_open (verify context)
  → run advance → branch diff + context validation → PROCEED assessment → seal receipts → transition → verify.intake.gate
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** Legacy `intake-checker.verify` worker remains in catalog docs only; flow binding removed.

## Runtime sequence (Step 1)

1. Incoming: `execute.commit.gate` **pass** (re-verify loops reuse same entry).
2. Visit admitted → `on_examine`: `prior-execute-commit-sealed`, `feature-branch-set`, `final-commit-recorded`.
3. `on_open`: `validate-manifest`, `validate-verify-context`.
4. Host / `run advance` calls `run_verify_intake_complete` when lifecycle is `opened`.
5. Engine captures `default...feature` diff, publishes `branch-diff` artifact, validates SHA/branch/diff usability.
6. Writes `run:receipts/assessment.md`, drafts and seals intake + agent receipts (`agent.mode: verify`).
7. On pass: patch `branch_diff_artifact_path` / `verify_diff_scope`, `transition` to `verify.intake.gate`.
8. On fail: seal blocked intake; visit stays opened (no route).

`operations.yaml`: author-only docgen (not bound in the flow registry). Mechanism lives in `verify_step_executor.py`.

## Contract (Step 2)

### Inputs

| When step opens | Source |
|-----------------|--------|
| `final_commit_sha`, `feature_branch`, `default_branch` | Execute phase state |
| `shape.record.plan`, `execute.commit.final-commit` | `nearest_sealed_ancestor` artifacts |
| Usable branch diff | Host `git diff` at complete |

### Outputs

| On pass | Output |
|---------|--------|
| Sealed visit, outcome `completed` | Route to `verify.intake.gate` |
| `verify.intake.branch-diff` artifact | Downstream verify steps |
| Intake + agent receipts | `verify.intake.gate` checks |

| On blocked validation | Output |
|-----------------------|--------|
| Intake receipt `status: blocked` | No transition |
| Assessment findings | Steward / operator remediation |

### Consumers

| Consumer | Uses |
|----------|------|
| `verify.intake.gate` | Sealed passed intake receipt |
| `verify.acceptance`+ | `verify.intake.branch-diff` |

## Minimal schema (Step 9)

```yaml
  - id: verify.intake
    kind: step
    title: Verify intake — branch diff, receipts, and plan alignment
    produces:
      artifacts:
      - id: branch-diff
        kind: document
        uri: run:artifacts/{visit_id}/branch.diff
        media_type: text/plain
    reads:
      state:
      - approved_ac
      - plan_path
      - feature_branch
      - default_branch
      - execution_graph_id
      artifacts:
      - artifact: shape.record.plan
        from: nearest_sealed_ancestor
      - artifact: execute.commit.final-commit
        from: nearest_sealed_ancestor
    allow:
      state:
      - verify_diff_scope
      - branch_diff_artifact_path
      - default_branch
    receipts:
    - registry:schemas/agent-receipt.schema.json
    - registry:schemas/intake-receipt.schema.json
    lifecycle:
      on_examine:
      - check: prior-execute-commit-sealed
      - check: feature-branch-set
      - check: final-commit-recorded
      on_open:
      - check: validate-manifest
      - check: validate-verify-context
      on_seal:
      - check: intake-receipt-sealed
        on_fail:
          action: reopen
          reason: Verify intake receipt not sealed
      - check: agent-receipt-sealed
        on_fail:
          action: reopen
          reason: Agent receipt not sealed
```

No `instructions`, `worker`, or steward `allow.cli`.

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| Worker bound on host-owned step | Remove `worker` from flow + catalog index |
| Legacy `registry:steps/verify-intake.md` | Drop flow reference; author `nodes/verify.intake/{doc,operations}.yaml` |
| `on_seal` only intake receipt | Add `agent-receipt-sealed` (align `execute.intake`) |
| Steward context | `render.py` engine-owned blurb for `verify.intake` |
| Context packet schema | Exempt `verify.intake` from required `instructions` |
| node-instructions.mdc | Verify intake ownership table |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_verify_evidence.py tests/unit/test_workflow_slices_2c_2f.py -q
pytest tests/unit/test_render.py -q -k "verify_intake"
pytest tests/unit/test_registry_refs.py -q
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | After commit gate pass, `run advance` seals verify.intake and reaches verify intake gate |
| AC2 | Flow has no worker binding for `verify.intake` |
| AC3 | Both intake and agent receipt checks on `on_seal` |
| AC4 | `run context` markdown describes host-owned verify intake (no worker table) |
| AC5 | Registry ref tests no longer require `verify-intake.md` in flow |

## Verification checklist

- [x] `flows/implementation/registry.yaml` node block: no worker/instructions; dual on_seal receipts.
- [x] `nodes/verify.intake/doc.yaml` + `operations.yaml`.
- [x] Catalog index + `node-instructions.mdc`.
- [x] `render.py` steward blurb.
- [x] Unit tests.
