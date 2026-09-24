---
step_id: implement.validate
title: Validate implementation against the brief
subagent: implementation-validator
run_modes: [implementation]
delivery_gate: false
state_keys:
  - steps.implement.validate.status
  - steps.implement.validate.receipt_id
---

## Purpose

Read-only check of what is actually on disk against the approved brief and acceptance criteria, before a human spends time on code review. Counts findings as critical / important / minor.

## Inputs (from parent)

- `approved_ac`, approved brief, `execution_graph_id`
- Builder receipts from `implement.build`

## Parent actions

1. Confirm every work item is completed before launching the validator:

```foundry-invoke
worker validator-ready --file "{run_dir}/execution-graph.json"
```

2. Assemble the validator packet (full graph + builder receipt summaries, not full transcripts):

```foundry-invoke
worker launch-packet --state "{state_path}"
```

Launch `implementation-validator` using the generated exact prompt and bounded inputs.

3. On critical findings, route to the graph owner before rework:

```foundry-invoke
worker route-critical --graph "{run_dir}/execution-graph.json" --findings '{findings_json}'
```

`transition --to implement.build --decision critical_findings` and re-run only the routed work items. Rework counters live in `state.rework`. Mutating rework marks `rework.post_repair_required`; the engine runs `verification.post_repair` after the repairer (or a repair work item) completes. Do not treat `graph add-repair-item` as verification — that command only schedules work.

4. Otherwise complete from `craft_staging_path` and `launch_id`, then transition using the durable `receipt_path`.

## State keys this step owns

- `steps.implement.validate.status`
- `steps.implement.validate.receipt_id`

## Gate

None. Requires `steps.implement.build.status == 'completed'`.

## Invalid transitions

- The validator is not a substitute for the human code review gate. `implement.code_review` still needs `human_approved: true`.
- Do not proceed past critical findings by re-classifying them.
