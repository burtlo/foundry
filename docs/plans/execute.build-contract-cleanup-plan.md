# Plan: `execute.build` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node review prompt](workflow-node-review-prompt.md), upstream [execute.plan contract cleanup](execute.plan-contract-cleanup-plan.md), pattern [execute.intake contract cleanup](execute.intake-contract-cleanup-plan.md), generated [nodes/execute.build.md](../nodes/execute.build.md).

## Goal

`execute.build` is a **host-owned deterministic step with no model worker on the happy path**: the engine runs manifest (or stub) build commands, records command exit evidence in an agent receipt, enforces `validate-build-exit` on seal, patches `last_build_exit_code`, and transitions to `execute.test`. Stewards use `run advance` (including the one-step **park** after first admission from plan or repair re-entry).

| Layer | Owner |
|-------|--------|
| **Judgment** | **None on happy path** — pass/fail is command exit codes + receipt checks |
| **Mechanism** | Engine: `run_execute_build_complete` via `run advance` when visit is `opened` (after park cleared) |
| **Policy** | `on_examine` graph + branch; `on_seal` `validate-build-exit` + `agent-receipt-sealed` (failed build reopens) |
| **Presentation** | Steward markdown blurb in `run context` (engine-owned step); `advance` may return `execute_build_boundary` once per visit |

Happy path:

```
execute.plan complete (or repair.limit.gate proceed) → admit execute.build
  → on_examine execution-graph-set + feature-branch-set
  → run advance parks once (execute_build_boundary or repair_reentry_boundary)
  → run advance → run_execute_build_complete → seal agent receipt → transition → execute.test
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** Task-registry / feature-builder agent paths remain catalog docs only; default host slice does not bind a worker.

## Runtime sequence (Step 1)

1. Incoming: sealed `execute.plan` or `execute.repair.limit.gate` **proceed** (repair loop).
2. Visit admitted → `on_examine`: `execution-graph-set`, `feature-branch-set`.
3. First `run advance` on `opened` may **park** (`execute_build_parked_visit_id`) when admission is from plan→build or repair→build.
4. Second `run advance` calls `run_execute_build_complete`:
   - `_commands_for_build`: stub when `FOUNDRY_EXECUTE_STUB=1`, else `commands.build` from app manifest, else zero-exit stub.
   - Seal `feature-builder` agent receipt (`agent.mode: engine`) with `commands[]`.
   - Patch `last_build_exit_code`.
   - `transition` toward seal; `on_seal` runs `validate-build-exit` (non-zero exits → reopen).
5. Route to `execute.test` on completed seal.

`operations.yaml`: author-only docgen (not bound in the flow registry). Mechanism lives in `execute_step_executor.py` and `advance.py` (park boundary).

## Contract (Step 2)

### Inputs

| When step opens | Source |
|-----------------|--------|
| `execution_graph_id`, `feature_branch` | Prior execute steps / branch |
| `execute.plan.execution-graph` | `nearest_sealed_ancestor` artifact (context reads) |
| `commands.build` (optional) | `.foundry/app.yaml` when not stubbing |

### Outputs

| On pass | Output |
|---------|--------|
| Sealed visit, outcome `completed` | Route to `execute.test` |
| Agent receipt with passing `commands[]` | `prior-execute-build-sealed`, `validate-build-exit` |
| `last_build_exit_code` | Telemetry / downstream diagnostics |

| On failed build commands | Output |
|--------------------------|--------|
| Agent receipt `status: failed` | `validate-build-exit` fails → visit **reopens** |

### Consumers

| Consumer | Uses |
|----------|------|
| `execute.test` | `prior-execute-build-sealed` on examine |
| Repair loop | Re-enters `execute.build` after test gate repair |

## Minimal schema (Step 9)

```yaml
  - id: execute.build
    kind: step
    title: Build graph work items — builders commit via CLI
    produces:
      artifacts: []
    reads:
      config:
      - builders
      - git
      state:
      - execution_graph_id
      - approved_ac
      - feature_branch
      artifacts:
      - artifact: execute.plan.execution-graph
        from: nearest_sealed_ancestor
    allow:
      state:
      - last_build_exit_code
    lifecycle:
      on_examine:
      - check: execution-graph-set
      - check: feature-branch-set
      on_seal:
      - check: validate-build-exit
        on_fail:
          action: reopen
          reason: Build exit validation failed
      - check: agent-receipt-sealed
    receipts: registry:schemas/agent-receipt.schema.json
```

No `instructions`, `worker`, `allow.files.write`, or steward `allow.cli`.

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| `registry:steps/execute-build.md` on flow step | Remove; author `nodes/execute.build/{doc,operations}.yaml` |
| Broad `workspace:` file write grant | Remove — host executor runs build; stewards do not need write cap |
| Steward context requires instructions | Add `execute.build` to `ENGINE_OWNED_STEP_NODE_IDS` + context-packet exemption |
| Steward markdown | `render.py` `## Execute build` blurb |
| `last_build_exit_code` patch | Explicit `allow.state` (top-level key, not node-scoped) |
| node-inventory / node-instructions.mdc | Engine-owned ownership row |

## Testing

```bash
cd /Users/lynnfrank/src/foundry/.cursor/foundry/cli
.venv/bin/python -m pytest tests/unit/test_execute_build_complete.py tests/unit/test_execute_test_gate.py tests/unit/test_render.py -q -k "execute_build or build_complete"
.venv/bin/python -m pytest tests/unit/test_registry_refs.py tests/acceptance/test_run_context.py -q -k "execute.build or execute_build"
.venv/bin/python foundry.py --json doc build --workspace /Users/lynnfrank/src/foundry --registry /Users/lynnfrank/src/foundry/.cursor/foundry
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | `run advance` after park runs build stub/commands, seals receipt, reaches `execute.test` (slice 2B) |
| AC2 | Flow has no `instructions` or `allow.files.write` for `execute.build` |
| AC3 | `validate-build-exit` still enforced on `on_seal` |
| AC4 | `run context` markdown describes host-owned build (no Instructions/Judgment) |
| AC5 | Catalog index lists `authoring: registry:nodes/execute.build/doc.yaml` |

## Deferred

- **Graph work-item coverage:** Engine does not yet prove each execution-graph work item has a corresponding code change; product gap noted in [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md).
- **`execute.test` contract cleanup:** Same engine-owned pattern; still references `registry:steps/execute-test.md` and repairer worker binding.
- **Remove `context_budget`** on build if no longer needed after instructions removal (left unchanged — harmless).
- **Feature-builder worker catalog** binding for non-host operator flows (out of default slice scope).

## Verification checklist

- [x] `flows/implementation/registry.yaml` node block: no instructions/files allow; `allow.state` for exit code.
- [x] `nodes/execute.build/doc.yaml` + `operations.yaml`.
- [x] Catalog index + `node-instructions.mdc` + `node-inventory.md`.
- [x] `constants.py`, `context-packet.schema.json`, `render.py`.
- [x] Unit + targeted acceptance tests.
- [x] `doc build` → `docs/nodes/execute.build.md`.
