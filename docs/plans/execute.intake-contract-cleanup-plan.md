# Plan: `execute.intake` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node review prompt](workflow-node-review-prompt.md), upstream [execute.start contract cleanup](execute.start-contract-cleanup-plan.md) (**done**), pattern [shape.intake](../../.cursor/foundry/nodes/shape.intake/operations.yaml), generated [nodes/execute.intake.md](../nodes/execute.intake.md).

## Goal

`execute.intake` is a **host-owned deterministic step with no model worker on the happy path**: the engine admits the visit, enforces prerequisites and git cleanliness, validates frozen shape artifacts, writes assessment + receipts, and transitions on pass. The steward does **not** orchestrate receipt mechanics or invoke `intake-checker.execute` on the default path.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None on happy path** — pass/blocked is deterministic validation |
| **Mechanism** | Engine: `run_execute_intake_complete` via `run advance` when visit is `opened` |
| **Policy** | `on_examine` AC + sealed record; `on_open` manifest + `validate-git-clean-execute`; blocked intake cannot transition |
| **Presentation** | Steward markdown blurb in `run context` (engine-owned step); blocked summary from receipts |

Happy path:

```
execute.start accept → admit execute.intake → on_examine + on_open (git clean)
  → run advance → validate frozen plan/AC → PROCEED assessment → seal receipts → transition → execute.intake.gate
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** Legacy `intake-checker.execute` worker remains in catalog docs only; flow binding removed.

## Runtime sequence (Step 1)

1. Incoming: `execute.start` **accept** or `verify.acceptance.gate` **rework_execute** (loop).
2. Visit admitted → `on_examine`: `approved-ac-recorded`, `prior-shape-record-sealed`.
3. `on_open`: `validate-manifest`, `validate-git-clean-execute` (halt if dirty).
4. Host / `run advance` calls `run_execute_intake_complete` when lifecycle is `opened`.
5. Engine validates `approved_ac`, digest fields, `plan_path`, plan body contains AC text.
6. Writes `run:receipts/assessment.md`, drafts and seals intake + agent receipts (`agent.mode: engine`).
7. On pass: patch `intake_path` / `entry_reason`, `transition` to `execute.intake.gate`.
8. On fail: seal blocked intake; visit stays opened (no route).

`operations.yaml`: author-only docgen (not bound in factory-flow). Mechanism lives in `execute_step_executor.py`.

## Contract (Step 2)

### Inputs

| When step opens | Source |
|-----------------|--------|
| `approved_ac`, `plan_path`, AC version/digest | Sealed `shape.record` state |
| `shape.record.plan` | `nearest_sealed_ancestor` artifact |
| Clean git worktree | `validate-git-clean-execute` on admit |
| `entry_reason` | Optional; rework loop may set |

### Outputs

| On pass | Output |
|---------|--------|
| Sealed visit, outcome `completed` | Route to `execute.intake.gate` |
| `intake_path: shaped` | Downstream execute steps |
| Intake + agent receipts | `execute.intake.gate` checks |

| On blocked validation | Output |
|-----------------------|--------|
| Intake receipt `status: blocked` | No transition |
| Assessment findings | Steward / operator remediation |

### Consumers

| Consumer | Uses |
|----------|------|
| `execute.intake.gate` | Sealed passed intake receipt |
| `execute.branch`+ | `intake_path`, shape state |

## Minimal schema (Step 9)

```yaml
  - id: execute.intake
    kind: step
    title: Execute intake — plan alignment and clean git tree
    produces:
      artifacts: []
    reads:
      config:
      - workspace
      state:
      - approved_ac
      - plan_path
      - intake_path
      - entry_reason
      artifacts:
      - artifact: shape.record.plan
        from: nearest_sealed_ancestor
    allow:
      state:
      - intake_path
      - entry_reason
    receipts:
    - registry:schemas/agent-receipt.schema.json
    - registry:schemas/intake-receipt.schema.json
    lifecycle:
      on_examine:
      - check: approved-ac-recorded
      - check: prior-shape-record-sealed
      on_open:
      - check: validate-manifest
      - check: validate-git-clean-execute
      on_seal:
      - check: intake-receipt-sealed
        on_fail:
          action: reopen
          reason: Execute intake receipt not sealed
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
| Legacy `registry:steps/execute-intake.md` | Drop flow reference; author `nodes/execute.intake/{doc,operations}.yaml` |
| `on_seal` only intake receipt | Add `agent-receipt-sealed` (align `shape.intake`) |
| Steward context | `render.py` engine-owned blurb for `execute.intake` |
| node-instructions.mdc | Execute intake ownership table |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_execute_slice_2a.py tests/unit/test_advance.py tests/unit/test_registry_refs.py -q
pytest tests/unit/test_render.py -q -k "execute_intake"
pytest tests/acceptance/test_run_context.py -q -k "execute.intake"
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | After `start`, `run advance` seals execute.intake and reaches intake gate / branch |
| AC2 | Flow has no worker binding for `execute.intake` |
| AC3 | Both intake and agent receipt checks on `on_seal` |
| AC4 | `run context` markdown describes host-owned intake (no worker table) |
| AC5 | Registry ref tests updated (execute-intake step stub no longer required) |

## Verification checklist

- [x] `factory-flow.yaml` node block: no worker/instructions; dual on_seal receipts.
- [x] `nodes/execute.intake/doc.yaml` + `operations.yaml`.
- [x] Catalog index + `node-instructions.mdc`.
- [x] `render.py` steward blurb.
- [x] Unit + acceptance tests.
