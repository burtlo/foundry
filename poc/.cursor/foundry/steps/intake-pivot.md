---
step_id: intake.pivot
title: Resolve run mode and initialise registers
subagent: null
run_modes: [implementation, analysis]
delivery_gate: false
state_keys:
  - steps.intake.pivot.status
  - run_mode
  - risk_tier
  - risk_tier_source
  - pr_extras_register
---

## Purpose

Decide which flow the run follows and initialise the registers later steps append to. This is the only step allowed to change `run_mode`; `flow current` and `flow next` resolve the flow from it on every call.

## Inputs (from parent)

- FactoryConfig slice: `analysis.issue_types`, `jira`
- Ticket packet from `intake.jira` or `intake.free_text`

## Parent actions

1. Set `run_mode` to `analysis` when `issuetype.name` matches `config.analysis.issue_types`, otherwise `implementation`. Free-text runs default to `implementation` unless the human asks for analysis.
2. Suggest `risk_tier` from profile rules (human may override):

```foundry-invoke
risk-tier suggest --ac-count {n} --issue-type "{issuetype.name}"
```

Set `risk_tier` and `risk_tier_source` to `auto`, or `human_override` when the human overrides.
3. Initialise `pr_extras_register` to `[]`.
4. `transition --to intake.refine --set run_mode=...` and re-read `flow current`; a pivot to `analysis` changes which flow the engine walks.

## Launch packet (pass to Task; not parent work)

None.

## State keys this step owns

- `steps.intake.pivot.status`
- `run_mode`
- `risk_tier`
- `risk_tier_source`
- `pr_extras_register`

## Gate

None.

## Invalid transitions

- Do not change `run_mode` after this step. Abort and start a new run instead.
- Analysis runs never reach `implement.*` or `deliver.ship`; those steps do not exist in the analysis flow.
