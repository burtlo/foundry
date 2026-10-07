# Plan: `execute.commit` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [execute.test contract cleanup](execute.test-contract-cleanup-plan.md), generated [nodes/execute.commit.md](../nodes/execute.commit.md).

## Goal

`execute.commit` is a **host-owned deterministic step with no model worker on the happy path**: the engine checks out the feature branch, records a final git commit (empty allowed in stub mode), publishes `final-commit` (`git_commit` reference), patches `final_commit_sha` / `execute_commit_message`, seals a **commit-agent-labeled** agent receipt, and transitions to `execute.commit.gate`. Stewards use `run advance` only.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None on happy path** — commit message defaults from run slug when `execute_commit_message` unset |
| **Mechanism** | Engine: `run_execute_commit_complete` via `run advance` when visit is `opened` |
| **Policy** | `on_examine` `prior-execute-test-sealed`; `on_seal` `final-commit-recorded` + `agent-receipt-sealed` |
| **Presentation** | Steward markdown blurb in `run context` (`## Execute commit`); no Instructions/Judgment |

Happy path:

```
execute.test.gate pass → admit execute.commit
  → on_examine prior-execute-test-sealed
  → run advance → run_execute_commit_complete → seal agent receipt → transition → execute.commit.gate
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** Legacy `commit-agent` worker binding and `registry:steps/execute-commit.md` were misleading; catalog worker docs remain for optional manual use only.

## Runtime sequence (Step 1)

1. Incoming: sealed `execute.test.gate` with decision **pass** (or re-entry after repair loop completes tests again).
2. Visit admitted → `on_examine`: `prior-execute-test-sealed`.
3. `run advance` calls `run_execute_commit_complete`:
   - Resolve `feature_branch`, default commit message `foundry: finalize execute for {slug}`.
   - `_record_execute_commit`: stub (`FOUNDRY_EXECUTE_STUB`) or real git add/commit on branch.
   - Link `final-commit` artifact (`git:commit/{sha}`).
   - Patch `final_commit_sha`, `execute_commit_message`.
   - Seal `commit-agent` agent receipt (`agent.mode: execute`).
   - `transition` toward seal; `on_seal` runs `final-commit-recorded` + `agent-receipt-sealed`.
4. Route to `execute.commit.gate` on completed seal.

`operations.yaml`: author-only docgen. Mechanism in `execute_step_executor.py` and `advance.py`.

## Contract (Step 2)

### Inputs

| When step opens | Source |
|-----------------|--------|
| `feature_branch`, `execution_graph_id` | Prior execute steps |
| `execute.plan.execution-graph` | `nearest_sealed_ancestor` artifact (context reads) |
| `execute_commit_message` (optional) | Run state override for commit message |

### Outputs

| On complete seal | Output |
|------------------|--------|
| `final_commit_sha`, `execute_commit_message` | `execute.commit.gate`, `verify.intake` |
| `execute.commit.final-commit` artifact | `verify.intake` via `nearest_sealed_ancestor` |
| Sealed commit-agent receipt | `agent-receipt-sealed` |

### Consumers

| Consumer | Uses |
|----------|------|
| `execute.commit.gate` | `prior-execute-commit-sealed`, `final-commit-recorded` |
| `verify.intake` | `final-commit` artifact, branch diff |

## Minimal schema (Step 9)

```yaml
  - id: execute.commit
    kind: step
    title: Final summarizing commit on feature branch
    produces:
      artifacts:
      - id: final-commit
        kind: reference
        scheme: git_commit
    reads:
      config:
      - git
      state:
      - execution_graph_id
      - feature_branch
      artifacts:
      - artifact: execute.plan.execution-graph
        from: nearest_sealed_ancestor
    allow:
      state:
      - final_commit_sha
      - execute_commit_message
    lifecycle:
      on_examine:
      - check: prior-execute-test-sealed
      on_seal:
      - check: final-commit-recorded
        on_fail:
          action: reopen
          reason: Final commit not recorded
      - check: agent-receipt-sealed
    receipts: registry:schemas/agent-receipt.schema.json
```

No `instructions`, no `worker`, no `allow.cli`.

## Files touched

- `.cursor/foundry/flows/implementation/registry.yaml` — minimal node block
- `.cursor/foundry/nodes/execute.commit/doc.yaml`, `operations.yaml`
- `.cursor/foundry/cli/foundry_cli/constants.py`, `render.py`, `execute_step_executor.py` (`COMMIT_AGENT_NAME`)
- `.cursor/foundry/schemas/context-packet.schema.json`
- `.cursor/rules/node-instructions.mdc`
- `docs/plans/node-inventory.md`
- Tests: `test_execute_commit_complete.py`, `test_render.py`, `test_registry_refs.py`
- Remove legacy `registry:steps/execute-commit.md` binding (delete step stub file)

## Acceptance criteria

| ID | Criterion |
|----|-----------|
| AC1 | Flow has no `instructions` / `worker` / steward `allow.cli` on `execute.commit` |
| AC2 | `run advance` on opened `execute.commit` seals receipt and reaches `execute.commit.gate` (stub) |
| AC3 | `run context --markdown` shows `## Execute commit` without Instructions/Judgment |
| AC4 | `ENGINE_OWNED_STEP_NODE_IDS` and context-packet exemption include `execute.commit` |
| AC5 | Agent receipt uses `commit-agent` name (not repairer) |

Stop after `execute.commit`.
