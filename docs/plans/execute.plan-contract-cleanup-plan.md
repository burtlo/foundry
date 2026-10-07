# Plan: `execute.plan` contract cleanup

Status: **done** (implementer slice).

Related: [workflow node review prompt](workflow-node-review-prompt.md), upstream [execute.branch contract cleanup](execute.branch-contract-cleanup-plan.md), pattern [shape.record](shape.record-contract-cleanup-plan.md), generated [nodes/execute.plan.md](../nodes/execute.plan.md).

## Goal

`execute.plan` is a **judgment-bounded step with an engine-owned completion path** (mirror `shape.record`):

The model (`execute.plan` task) proposes `execution_graph` JSON and `execute_brief_markdown` from sealed shape plan + execute state, with PROCEED vs BLOCKED. Foundry validates, publishes artifacts, patches graph/brief state, seals the agent receipt, and transitions to `execute.build`.

| Layer | Owner |
|-------|--------|
| **Judgment** | Model: derive work-item graph and phase brief from sealed plan and approved AC |
| **Mechanism** | Engine: `visit plan complete` / `run advance` after PROCEED — publish, state patch, receipt, transition |
| **Policy** | `feature-branch-set`, `ensure-execution-graph-reference`, `execution-graph-set`, `agent-receipt-sealed` |
| **Presentation** | Steward markdown blurb in `run context` — not CLI orchestration prose |

Happy path:

```
execute.branch → execute.plan → agent wait (plan judgment) → run agent submit (PROCEED)
  → visit plan complete (or run advance) → seal + transition → execute.build
```

**Agent necessity (Step 6):** **B — Deterministic node with one bounded judgment operation.**

## Investigation summary

### Runtime before cleanup

1. **Dual path:** Host `run_execute_plan_complete` on every `run advance` (minimal stub graph) vs bound `planner` worker with steward `artifact.publish` / `transition` in `registry:steps/execute-plan.md`.
2. **`_HOST_IMPLEMENTED_STEP_NODES`** included `execute.plan` — no agent wait on the default host path.
3. **Schema:** `worker:` binding, broad `allow.files.write` / `allow.cli`, no task registry entry, no `visit.plan.complete`.

### Target flow registry node

```yaml
  - id: execute.plan
    kind: step
    title: Execution graph and phase-scoped internal brief
    produces:
      artifacts:
      - id: execution-graph
        kind: document
        uri: run:artifacts/{visit_id}/execution-graph.json
        media_type: application/json
      - id: execute-brief
        kind: document
        uri: run:artifacts/{visit_id}/execute-brief.md
        media_type: text/markdown
    instructions: registry:nodes/execute.plan/judgment.md
    reads:
      state:
      - approved_ac
      - approved_ac_digest
      - feature_branch
      - execution_graph_id
      artifacts:
      - artifact: shape.record.plan
        from: nearest_sealed_ancestor
    allow:
      cli:
      - run.agent.submit
      - visit.plan.complete
    receipts: registry:schemas/agent-receipt.schema.json
    context_budget:
      max_input_chars: 16000
      max_summary_chars: 4000
    lifecycle:
      on_examine:
      - check: feature-branch-set
      on_open:
      - check: ensure-execution-graph-reference
      on_seal:
      - check: execution-graph-set
      - check: agent-receipt-sealed
```

## Implementation slices

1. Task + schema: `tasks/execute.plan.yaml`, `schemas/execute-plan-result.schema.json`, `nodes/execute.plan/judgment.md`, `doc.yaml`, `operations.yaml` (docgen).
2. Engine: `run_execute_plan_complete` requires accepted task result; `visit.plan.complete` CLI; advance boundary wait + conditional complete (remove unconditional host auto-complete).
3. Flow + catalog + `node-instructions.mdc` + render blurb.
4. Tests: `test_execute_plan_complete.py`, `execute_plan.feature`; adjust `test_registry_refs` (no `execute-plan.md` / `planner` worker on node).
5. `doc build` → `docs/nodes/execute.plan.md`.

## Deferred

- Rich planner subagent prompt refresh beyond task `judgment.md` (legacy `agents/planner.md` remains for optional manual use).
- Replan loop (`verify.acceptance.gate` → `execute.plan`) dedicated acceptance fixture (covered indirectly via stub auto-dispatch in slice 2A).

Stop after `execute.plan`.
