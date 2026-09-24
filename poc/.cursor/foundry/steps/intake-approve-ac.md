---
step_id: intake.approve_ac
title: Approve acceptance criteria
subagent: null
run_modes: [implementation, analysis]
delivery_gate: false
state_keys:
  - steps.intake.approve_ac.status
  - steps.intake.approve_ac.approved
  - steps.intake.approve_ac.gate_decision
  - approved_ac
  - approved_ac_version
---

## Purpose

Collect the human decision after presentation and freeze scope. Writes `approved_ac[]` verbatim from `presented_ac` and bumps `approved_ac_version`. No builder or researcher may start until this step completes.

## Inputs (from parent)

- `presented_ac` from `intake.present_ac`

## Parent actions

1. Collect the decision: `approve`, `changes`, or `deeper_research` (implementation) / `approve` or `changes` (analysis).
2. On **approve**: copy `presented_ac` into `approved_ac` **verbatim** (same `id`, `text`, `source` for each item), set `approved_ac_version` to `(prior || 0) + 1`, then run `gate resolve --state "{state_path}" --config "{config_path}" --source human --decision approve`.
3. On **changes**: merge human edits into `presented_ac`, re-run `intake.present_ac` (rework to presentation).
4. On **deeper_research** (implementation only): stop or pivot — do not proceed to `plan.research`.
5. Before transitioning to research:

```foundry-invoke
intake validate-ac --state "{state_path}"
```

Exit 0 required.
6. `transition --to plan.research` or `analysis.research` with `--decision approve`.

## Launch packet (pass to Task; not parent work)

None.

## State keys this step owns

- `steps.intake.approve_ac.status`
- `steps.intake.approve_ac.approved`
- `steps.intake.approve_ac.gate_decision`
- `approved_ac`
- `approved_ac_version`

## Gate

`human_confirm` (`approve_ac`). Requires `approved_ac_version >= 1` and verbatim match between `presented_ac` and `approved_ac`. Blocks `plan.research` and `analysis.research`.

## Invalid transitions

- Paraphrasing or reordering AC between `presented_ac` and `approved_ac` fails `intake validate-ac`.
- Do not proceed when grilling left unresolved questions without `assumptions` and `accept_risk`.
