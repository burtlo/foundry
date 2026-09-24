---
step_id: implement.build
title: Build and test
subagent: null
run_modes: [implementation]
delivery_gate: false
orchestrator_contract: strict
state_keys:
  - steps.implement.build.status
  - steps.implement.build.receipt_id
---

## Orchestrator contract (this step only)

**Role:** Traffic cop. **You do not edit code. You do not edit tests. You do not write receipts.**

### Allowed tools

- Foundry CLI via `foundry-invoke` / `steward_allowlist` (worker, build-step, observability, transition, run block)
- `Task` subagent: `backend-builder`, `client-builder`, `feature-builder`, **`repairer`**

### Forbidden

- Any edit under `{app_folder}` except `.foundry/runs/...` non-receipt files explicitly required by CLI
- `Write`/`StrReplace` on `receipts/*.json` or staging identity fields
- Raw `dotnet build` / `dotnet test`
- Advancing when `build-step verify` exit != 0

### Loop

1. `worker next-builder` until `done: true`
2. Per item: `worker launch-packet` → **Task** using the exact generated prompt → worker writes only `craft_staging_path` → `observability subagent complete` → `worker complete-item`
3. `build-step verify` — **must succeed**; use returned `receipt_path` only
4. `transition --to implement.validate --evidence <receipt_path>`

### On `build-step verify` failure

1. `run block --reason "..."`
2. Ask human: **immediate repairer Task** OR **add repair work item**
3. After repairer completes, re-run `build-step verify` from step 3
4. Do **not** transition until verify succeeds

### On rework (`fix_findings`, `critical_findings`, `code_changes`)

- If graph is complete: `graph add-repair-item` or human-approved repair scope before inline builder work
- Never implement fixes in parent context

## Purpose

Execute the approved execution graph. Builders write code and tests together; the parent orchestrates and never implements inline.

## Inputs (from parent)

- `execution_graph_id` and the work items in `ready` state
- `approved_ac`
- FactoryConfig slice: `templates.implement`, `templates.add_tests`, `templates.run_tests`, path globs
- Receipts from dependency work items

## Parent actions

You are the **orchestrator only** on this step. Prefer `flow orchestrator-packet` when `foundry.orchestrator.thin_context` is true. Subagents come from `builder-packet`, not `flow current`.

1. Ask for the next ready work item:

```foundry-invoke
worker next-builder --state "{state_path}" --graph "{run_dir}/execution-graph.json" --config "{config_path}"
```

Repeat until `"done": true`.

2. For each ready ID, launch the packet's `subagent` with the packet's `subagent_mode` (`implement` or `repair`):

```foundry-invoke
worker launch-packet --state "{state_path}" --work-item {id}
```

Use the generated launch packet. Never edit app source in the parent context.

3. After the builder (or repairer) finishes, complete observability and record the graph item. The subagent writes only to `craft_staging_path`:

```foundry-invoke
observability subagent complete --state "{state_path}" --receipt {craft_staging_path} --launch-id {launch_id}
```

```foundry-invoke
worker complete-item --file "{run_dir}/execution-graph.json" --work-item {id} --receipt {receipt_id} --state "{state_path}"
```

4. When all work items are complete, verify build and tests. The CLI writes the step receipt:

```foundry-invoke
build-step verify --state "{state_path}" --graph "{run_dir}/execution-graph.json" --config "{config_path}"
```

5. `transition --to implement.validate` using the `build-step verify` `receipt_path` as `--evidence`.

Tests use `Subject_Scenario_ExpectedOutcome` naming.

## Repairer path

When `build-step verify` fails and the graph has no ready builder items:

```foundry-invoke
run block --state "{state_path}" --reason "{errorCode}: {message}" --step-id implement.build
```

```foundry-invoke
graph add-repair-item --file "{run_dir}/execution-graph.json" --state "{state_path}" --id repair-build-verify-1 --reason "{reason}"
```

Then `worker next-builder` returns the repair item (`owner: repairer`). Launch **repairer** in `repair` mode, complete it, re-run `build-step verify`.

Immediate `Task(repairer)` is allowed after a human chooses that option. Still record launch/complete via CLI.

## State keys this step owns

- `steps.implement.build.status`
- `steps.implement.build.receipt_id`
- `steps.implement.build.build_step_verify_receipt_id` (CLI-owned)

## Gate

None. Requires `state.feature_branch`.

## Invalid transitions

- The parent must not inline builder or repairer work in its own context.
- The parent must not hand-write receipts or run raw `dotnet` to bypass `build-step verify`.
- Rework arrives here from `implement.validate` (`critical_findings`), `implement.code_review` (`code_changes`), and `implement.pre_pr_review` (`fix_findings`). Each of those re-runs validation and code review afterwards.
