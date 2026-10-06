# Plan: `execute.test` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [execute.build contract cleanup](execute.build-contract-cleanup-plan.md), generated [nodes/execute.test.md](../nodes/execute.test.md).

## Goal

`execute.test` is a **host-owned deterministic step with no model worker on the happy path**: the engine runs manifest (or stub) verification commands, records command exit evidence in a **repairer-labeled** agent receipt (`agent.mode: repair` for catalog alignment only), patches `last_test_exit_code` and `repair_loop_count`, and transitions to `execute.test.gate`. Stewards use `run advance` only.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None on happy path** — pass/repair routing is `execute.test.gate` (engine) from receipt exit codes |
| **Mechanism** | Engine: `run_execute_test_complete` via `run advance` when visit is `opened` |
| **Policy** | `on_examine` `prior-execute-build-sealed`; `on_seal` `agent-receipt-sealed` |
| **Presentation** | Steward markdown blurb in `run context` (`## Execute test`); no Instructions/Judgment |

Happy path:

```
execute.build sealed → admit execute.test
  → on_examine prior-execute-build-sealed
  → run advance → run_execute_test_complete → seal agent receipt → transition → execute.test.gate
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** The repairer worker binding in legacy flow was misleading; receipt uses `repairer` agent name for gate semantics, not `run.agent.submit` on the default path.

## Runtime sequence (Step 1)

1. Incoming: sealed `execute.build`.
2. Visit admitted → `on_examine`: `prior-execute-build-sealed`.
3. `run advance` calls `run_execute_test_complete`:
   - `_verification_policy`: `implementation` unless prior `connection.taken` with `loop: repair`.
   - `_commands_for_test`: stub when `FOUNDRY_EXECUTE_STUB=1`, else manifest `verification.{policy}` command names.
   - Seal `repairer` agent receipt (`agent.mode: repair`) with `commands[]` and `verification_policy` output.
   - Patch `last_test_exit_code`, `repair_loop_count`.
   - `transition` toward seal.
4. `execute.test.gate` maps receipt commands to **pass** | **repair**.

`operations.yaml`: author-only docgen. Mechanism in `execute_step_executor.py` and `advance.py`.

## Contract (Step 2)

### Inputs

| When step opens | Source |
|-----------------|--------|
| `execution_graph_id`, `feature_branch` | Prior execute steps |
| `execute.plan.execution-graph` | `nearest_sealed_ancestor` artifact (context reads) |
| `verification` policies | `.foundry/app.yaml` |

### Outputs

| On complete seal | Output |
|------------------|--------|
| Agent receipt with `commands[]` | `execute.test.gate` pass/repair decision |
| `last_test_exit_code`, `repair_loop_count` | Telemetry / repair limit gate |

### Consumers

| Consumer | Uses |
|----------|------|
| `execute.test.gate` | Sealed receipt exit codes |
| `execute.repair.limit.gate` | Repair loop count |

## Minimal schema (Step 9)

```yaml
  - id: execute.test
    kind: step
    title: Run repo verification and repair loop
    produces:
      artifacts: []
    reads:
      config:
      - verification
      state:
      - execution_graph_id
      - feature_branch
      artifacts:
      - artifact: execute.plan.execution-graph
        from: nearest_sealed_ancestor
    allow:
      state:
      - last_test_exit_code
      - repair_loop_count
    lifecycle:
      on_examine:
      - check: prior-execute-build-sealed
      on_seal:
      - check: agent-receipt-sealed
    receipts: registry:schemas/agent-receipt.schema.json
```

No `instructions`, no `worker`.

## Files touched

- `.cursor/foundry/flows/factory-flow.yaml` — minimal node block
- `.cursor/foundry/nodes/execute.test/doc.yaml`, `operations.yaml`
- `.cursor/foundry/cli/foundry_cli/constants.py`, `render.py`
- `.cursor/foundry/schemas/context-packet.schema.json`
- `.cursor/rules/node-instructions.mdc`
- `docs/plans/node-inventory.md`
- Tests: `test_execute_test_complete.py`, `test_render.py`, `test_registry_refs.py`
- Removed legacy `registry:steps/execute-test.md` binding (delete step stub file)

## Acceptance criteria

| ID | Criterion |
|----|-----------|
| AC1 | Flow has no `instructions` / `worker` on `execute.test` |
| AC2 | `run advance` on opened `execute.test` seals receipt and reaches `execute.test.gate` (stub) |
| AC3 | `run context --markdown` shows `## Execute test` without Instructions/Judgment |
| AC4 | `ENGINE_OWNED_STEP_NODE_IDS` includes `execute.test` |
