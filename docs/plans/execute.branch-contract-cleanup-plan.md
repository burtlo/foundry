# Plan: `execute.branch` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node review prompt](workflow-node-review-prompt.md), upstream [execute.intake.gate contract cleanup](execute.intake.gate-contract-cleanup-plan.md) (**done**), pattern [execute.intake](../../.cursor/foundry/nodes/execute.intake/operations.yaml), generated [nodes/execute.branch.md](../nodes/execute.branch.md).

## Goal

`execute.branch` is a **host-owned deterministic step with no model worker**: the engine admits the visit after sealed passed `execute.intake`, computes the feature branch name, runs git checkout/create, patches branch + graph reference state, and transitions to `execute.plan`. The steward does **not** create branches manually or patch state on the happy path.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None** — branch naming rules and git operations are deterministic |
| **Mechanism** | Engine: `run_execute_branch_complete` via `run advance` when visit is `opened` |
| **Policy** | `on_examine`: `prior-execute-intake-sealed`; branch name regex `foundry/…` in executor |
| **Presentation** | Steward markdown blurb in `run context` (engine-owned step) |

Happy path:

```
execute.intake.gate pass → admit execute.branch → on_examine
  → run advance → git default branch + feature branch → patch state → transition → execute.plan
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** Legacy `registry:steps/execute-branch.md` prose moves to `nodes/execute.branch/` for docgen only.

## Runtime sequence (Step 1)

1. Incoming: `execute.intake.gate` **pass** (sealed passed intake receipt).
2. Visit admitted → `on_examine`: `prior-execute-intake-sealed`.
3. Host / `run advance` calls `run_execute_branch_complete` when lifecycle is `opened`.
4. Engine resolves `default_branch`, computes `feature_branch` from `run_slug` / optional `developer_first_name`, validates `foundry/…` pattern.
5. Git: checkout existing branch or `checkout -b` from default.
6. Patches `default_branch`, `feature_branch`, `feature_branch_head`, `execution_graph_id` (`{run_slug}:execution-graph`).
7. `transition_visit` to `execute.plan`.

`operations.yaml`: author-only docgen (not bound in the flow registry). Mechanism lives in `execute_step_executor.py`; routing in `advance.py`.

## Contract (Step 2)

### Inputs

| When step opens | Source |
|-----------------|--------|
| Sealed passed `execute.intake` | `prior-execute-intake-sealed` |
| `run_slug`, optional `developer_first_name` | Run state |
| Git workspace | `reads.config.git` (implicit via workspace) |

### Outputs

| On success | Output |
|------------|--------|
| Sealed visit, outcome `completed` | Route to `execute.plan` |
| `feature_branch`, `feature_branch_head`, `default_branch` | `feature-branch-set` check on `execute.plan` |
| `execution_graph_id` placeholder | `ensure-execution-graph-reference` on `execute.plan` open |

### Failure conditions

| Failure | Kind |
|---------|------|
| Invalid branch name | Deterministic (`BRANCH_NAME_INVALID`) |
| Git checkout/create errors | Infrastructure |
| State patch rejected | Invalid workflow / schema (should not occur with correct `allow.state`) |

### Consumers

| Consumer | Uses |
|----------|------|
| `execute.plan` | `feature_branch`, `execution_graph_id` |
| Downstream execute / verify | Branch identity in state |

## Responsibility table (Step 3)

| Responsibility | Current owner | Category | Recommended owner | Evidence |
|----------------|---------------|----------|-------------------|----------|
| Branch name computation | Host executor | MECHANISM | Engine | `_expected_feature_branch` |
| Git branch create/checkout | Host executor | MECHANISM | Engine | `_ensure_feature_branch` |
| State patch + transition | Host executor | MECHANISM | Engine | `run_execute_branch_complete` |
| Steward git instructions | `steps/execute-branch.md` | PRESENTATION/DELETE | Renderer blurb | No agent on path |
| `allow.state` grants | Flow schema | POLICY | Flow (engine-only keys) | `patch_allowed` enforcement |

## Minimal schema (Step 9)

```yaml
  - id: execute.branch
    kind: step
    title: Create the feature branch
    produces:
      artifacts: []
    reads:
      config:
      - git
      state:
      - run_slug
      - developer_first_name
    allow:
      state:
      - default_branch
      - feature_branch
      - feature_branch_head
      - execution_graph_id
    lifecycle:
      on_examine:
      - check: prior-execute-intake-sealed
```

No `instructions`, `worker`, or steward `allow.cli`. `allow.state` lists only keys the engine patches (not steward-facing capability).

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| Legacy `registry:steps/execute-branch.md` on flow | Drop flow reference; author `nodes/execute.branch/{doc,operations}.yaml` |
| Steward context still loads step instructions | `ENGINE_OWNED_STEP_NODE_IDS` + `render.py` blurb |
| Catalog / docs | `authoring: registry:nodes/execute.branch/doc.yaml`; `doc build` |
| Registry ref tests | Remove `execute-branch.md` from required step stubs |
| node-instructions.mdc | Execute branch ownership table |

## Testing

```bash
cd .cursor/foundry/cli
.venv/bin/python -m pytest tests/unit/test_execute_intake.py tests/unit/test_advance.py tests/unit/test_registry_refs.py -q
.venv/bin/python -m pytest tests/unit/test_render.py -q -k "execute_branch"
.venv/bin/python -m pytest tests/acceptance/test_run_context.py -q -k "execute.branch"
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | After intake gate pass, `run advance` seals branch step and sets `feature_branch` / `execution_graph_id` |
| AC2 | Flow has no `instructions` for `execute.branch` |
| AC3 | `run context` markdown describes host-owned branching (no Instructions/Judgment sections) |
| AC4 | Registry ref tests no longer require `execute-branch.md` stub |

## Verification checklist

- [x] `flows/implementation/registry.yaml` node block: no instructions.
- [x] `nodes/execute.branch/doc.yaml` + `operations.yaml`.
- [x] Catalog index + `node-instructions.mdc`.
- [x] `constants.py`, `context-packet.schema.json`, `render.py`.
- [x] Unit + acceptance tests.
- [x] `doc build` → `docs/nodes/execute.branch.md`.

Stop after `execute.branch` — do not expand into `execute.plan`.
