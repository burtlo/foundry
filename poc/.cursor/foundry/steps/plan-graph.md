---
step_id: plan.graph
title: Execution graph
subagent: planner
run_modes: [implementation]
delivery_gate: false
state_keys:
  - steps.plan.graph.status
  - steps.plan.graph.approved
  - steps.plan.graph.human_approved
  - execution_graph_id
---

## Purpose

Materialize the execution contract for every risk tier. Low-risk runs use an engine-generated one-node graph owned by the snapshot `builders.default_owner`; medium/high runs use planner decomposition.

## Inputs (from parent)

- Approved brief from `plan.brief` (`brief.md` / brief_snapshot)
- `approved_ac`, `risk_tier`
- Schema: `schemas/execution-graph.schema.json`
- Launch packet rules: `.cursor/foundry/docs/worker-launch-contract.md`

## Parent actions

**Traffic cop only.** Do not draft or Write `{run_dir}/execution-graph.json`.

For low risk, the transition into this step has already generated `{run_dir}/execution-graph.json`; skip planner launch and continue at validation.

For medium/high risk:

1. Generate the launch packet:

```foundry-invoke
worker launch-packet --state "{state_path}"
```

2. Launch Task with its exact prompt and complete from its `craft_staging_path`. Planner alone writes the returned `named_artifact_path`.
4. Validate:

```foundry-invoke
graph validate --file "{run_dir}/execution-graph.json" --state "{state_path}"
```

5. Gate:
   - `drive_to_pr`: after validate succeeds, `gate resolve --source auto --decision approve --graph-validated`.
   - Otherwise present graph and collect human decision.
6. On approve, run `gate resolve --state "{state_path}" --config "{config_path}" --source human --decision approve`. The engine records `execution_graph_id` from the validated artifact.
7. If the graph changes after `implement.build` has started:

```foundry-invoke
graph record-change --file "{run_dir}/execution-graph.json" --after-build-started
```

8. Hard gate → `run handoff` and stop unless keep going.

## State keys this step owns

- `steps.plan.graph.status`
- `steps.plan.graph.approved`
- `steps.plan.graph.human_approved`
- `execution_graph_id`

## Gate

`human_approval` (`approve_graph`). Auto-eligible under `drive_to_pr` only after `graph validate` and `gate resolve --graph-validated`. Blocks `implement.branch` and `implement.build`.

## Invalid transitions

- Parent must not author or persist `execution-graph.json`.
- Builders do not start before this gate.
