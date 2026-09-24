---
step_id: plan.brief
title: Implementation brief
subagent: planner
run_modes: [implementation]
delivery_gate: false
state_keys:
  - steps.plan.brief.status
  - steps.plan.brief.approved
  - steps.plan.brief.human_approved
  - steps.plan.brief.gate_decision
---

## Purpose

Turn approved acceptance criteria plus research into a scoped plan the human signs off on: what changes, where, how it is tested, and what is deliberately not being done.

## Inputs (from parent)

- `approved_ac`, `assumptions`
- `steps.plan.research.receipt_id` and its receipt **summary** only
- FactoryConfig / project_context
- Launch packet rules: `.cursor/foundry/docs/worker-launch-contract.md`

## Parent actions

**Traffic cop only.** Do not write `brief.md` yourself.

1. Generate the launch packet:

```foundry-invoke
worker launch-packet --state "{state_path}"
```

2. Launch Task with its exact prompt and complete from its `craft_staging_path`. Planner alone writes the returned `named_artifact_path`.
4. Snapshot:

```foundry-invoke
plan record-brief --state "{state_path}" --brief-file "{run_dir}/brief.md"
```

5. Gate:
   - `drive_to_pr`: when brief is recorded, `gate resolve --source auto --decision approve` (engine confirms eligibility).
   - `interactive` / `plan_control`: `observability gate present`, then human decision.
6. On approve, run `gate resolve --state "{state_path}" --config "{config_path}" --source human --decision approve`, write the required handoff, then transition to `plan.graph` from the next steward session.
7. Session stop after hard gate unless user said keep going; `run handoff`.

## State keys this step owns

- `steps.plan.brief.status`
- `steps.plan.brief.approved`
- `steps.plan.brief.human_approved`
- `steps.plan.brief.gate_decision`
- brief_snapshot / brief_path (via plan record-brief)

## Gate

`human_approval` (`approve_brief`). Auto-eligible under `drive_to_pr` after `plan record-brief`. Blocks `plan.graph`, `implement.branch`, and `implement.build`.

## Invalid transitions

- Parent must not author the brief.
- No branch and no code before this gate resolves.
- `revise_research` returns to `plan.research`.
