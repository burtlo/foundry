# Plan: `shape.record` contract cleanup

Status: **done** (implemented in this session)

Related: [workflow node review prompt](workflow-node-review-prompt.md), upstream [shape-present-contract-cleanup-plan](shape-present-contract-cleanup-plan.md), sibling [shape.present.gate](shape-present-gate-contract-cleanup-plan.md), generated [nodes/shape.record.md](../nodes/shape.record.md).

## Goal

`shape.record` is a **judgment-bounded step with an engine-owned completion path** (mirror `shape.present`):

The model (`shape.record` task) proposes living `plan_markdown` and frozen `approved_ac`, with PROCEED vs BLOCKED. Foundry validates, patches record state, publishes `plan`, mirrors `workspace:plan.md`, seals the agent receipt, and transitions to `shape.record.gate`.

| Layer | Owner |
|-------|--------|
| **Judgment** | Model: derive approved AC and living plan from presentation state |
| **Mechanism** | Engine: `visit record complete` / `run advance` after PROCEED — publish, state patch, workspace mirror, receipt, transition |
| **Policy** | `prior-present-sealed`, `approved-ac-recorded`, `agent-receipt-sealed` on seal; BLOCKED → receipt only on submit |
| **Presentation** | `shape.record.gate` two-turn UX — not steward CLI orchestration |

Happy path:

```
shape.present.gate accept → shape.record → agent wait (record judgment) → run agent submit (PROCEED)
  → visit record complete (or run advance) → seal + transition → shape.record.gate
```

**Testing principle:** `@node.shape.record` acceptance proves submit + `visit record complete` and policy denials. Unit tests cover executor and flow `allow.cli`. Remove scenarios that certify manual `ledger show` → `state_patch` → publish → `receipt seal` → `transition` as the product contract.

**Agent necessity (Step 6):** **B — Deterministic node with one bounded judgment operation.**

## Investigation summary (Steps 1–2)

### Runtime before cleanup

1. **Dual path:** Steward `instructions.md` orchestration vs `run_shape_record_complete` on `run advance` (host template plan from `presented_ac`, no agent).
2. **`HOST_OWNED_SHAPE_STEP_NODES`** included only `shape.record` — blocked agent wait, forced host completion.
3. **Schema:** `worker:` binding, broad `allow.cli` / `allow.files.write`, no task registry entry, no `visit.record.complete`.

### Current factory-flow node (reference)

```yaml
  - id: shape.record
    kind: step
    title: Shape record — freeze approved_ac and living plan
    produces:
      artifacts:
      - id: plan
        kind: document
        uri: run:artifacts/{visit_id}/plan.md
        media_type: text/markdown
    instructions: registry:nodes/shape.record/instructions.md
    reads:
      state:
      - presented_ac
      - presentation_artifact_path
      artifacts:
      - artifact: shape.present.presentation
        from: nearest_sealed_ancestor
    allow:
      state: [approved_ac, approved_ac_version, approved_ac_digest, plan_path, plan_version]
      files.write: [workspace:plan.md, run artifacts, receipts]
      cli: [artifact.publish, ledger.show, receipt.link, transition, visit.state_patch]
    worker:
      prompt: registry:agents/shape-recorder.md
      contract: registry:workers/shape-recorder/contract.yaml
      mode: shape
    receipts: registry:schemas/agent-receipt.schema.json
    lifecycle:
      on_examine: [prior-present-sealed]
      on_seal: [approved-ac-recorded, agent-receipt-sealed]
```

### Consumers

| Consumer | Needs |
|----------|--------|
| `shape.record.gate` | `approved_ac`, digest, `plan_path`, `shape.record.plan` |
| `execute.intake`, `execute.plan`, verify nodes | Sealed `shape.record.plan` |

## Target contract

```yaml
  - id: shape.record
    kind: step
    title: Shape record — freeze approved_ac and living plan
    produces:
      artifacts:
      - id: plan
        kind: document
        uri: run:artifacts/{visit_id}/plan.md
        media_type: text/markdown
    instructions: registry:nodes/shape.record/judgment.md
    reads:
      state:
      - presented_ac
      - presentation_artifact_path
      - approved_ac
      artifacts:
      - artifact: shape.present.presentation
        from: nearest_sealed_ancestor
    allow:
      cli:
      - run.agent.submit
      - visit.record.complete
    receipts: registry:schemas/agent-receipt.schema.json
    lifecycle:
      on_examine:
      - check: prior-present-sealed
      on_seal:
      - check: approved-ac-recorded
        on_fail:
          action: reopen
          reason: approved_ac not recorded
      - check: agent-receipt-sealed
        on_fail:
          action: reopen
          reason: Shape record receipt not sealed
```

## Implementation slices

| Slice | Work |
|-------|------|
| 1 | `judgment.md`, `shape-record-result.schema.json`, `tasks/shape.record.yaml` |
| 2 | `visit.record.complete` CLI + `run_shape_record_complete` uses accepted PROCEED result |
| 3 | Agent dispatch/submit (wait, BLOCKED receipt, supersede), remove `HOST_OWNED` for record |
| 4 | `factory-flow.yaml`, catalog index, `doc.yaml`, render steward blurb |
| 5 | Acceptance + unit tests; `shape_phase_e2e` record/present agent paths |
| 6 | Docs (`docs/nodes/shape.record.md`, CLI index + `visit-record-complete.md`) |

## Test plan

```bash
cd .cursor/foundry/cli && python -m pytest tests/unit/test_shape_record_complete.py tests/unit/test_engine.py::test_shape_record_capability_contract -q
python -m pytest tests/acceptance/test_shape_record.py -q
python -m pytest tests/acceptance/test_shape_phase_e2e.py -q
```

## Deferred

- `shape.record.gate` contract cleanup (next orchestration node).
- Rich assessment.md artifact in engine (judgment is schema-only; receipt uses summary).
