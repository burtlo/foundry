---
step_id: plan.research
title: Codebase research
subagent: codebase-researcher
run_modes: [implementation]
delivery_gate: false
state_keys:
  - steps.plan.research.status
  - steps.plan.research.receipt_id
---

## Purpose

Map the part of the codebase the approved acceptance criteria touch, before anyone writes a brief. Read-only. Produces the RelevantFiles / ArchitectureSummary / Patterns / Risks / Gaps packet the brief is built from.

## Inputs (from parent)

- `approved_ac`, `assumptions`, `risk_tier`
- `app_folder`
- FactoryConfig slice for `codebase-researcher` (`app_folder`, `factory_root`)

## Parent actions

1. Generate and atomically record the launch:

```foundry-invoke
worker launch-packet --state "{state_path}"
```

2. Launch `task_subagent_type` with the returned exact `prompt`, bounded `config`/`inputs`, and `allowed_writes`. Complete it from `craft_staging_path` and `launch_id`.
3. `transition --to plan.brief --evidence <receipt_path from complete>`.

Parallel read-only research subagents are allowed here. Never run a builder in parallel with research.

## State keys this step owns

- `steps.plan.research.status`
- `steps.plan.research.receipt_id`

## Gate

None. Requires `steps.intake.approve_ac.approved` and `approved_ac_version >= 1`.

## Invalid transitions

- No file edits in this step. Findings that imply edits become work items in `plan.graph`.
- Research that invalidates the acceptance criteria goes back through `plan.brief --decision revise_research`, not forward.
