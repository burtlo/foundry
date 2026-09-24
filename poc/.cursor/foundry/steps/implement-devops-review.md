---
step_id: implement.devops_review
title: devops-builder pre-PR workflow review
subagent: devops-builder
run_modes: [implementation]
delivery_gate: true
state_keys:
  - steps.implement.devops_review.status
  - steps.implement.devops_review.report
  - steps.implement.devops_review.approved
  - steps.implement.devops_review.human_approved
---

## Purpose

Review GitHub Actions changes and pin action references to full commit SHAs before the PR exists. Runs when `config.devops.enabled` and `config.devops.run_before_pr` are both true; otherwise the engine skips it and `delivery-check` does not require it.

## Inputs (from parent)

- FactoryConfig slice: `devops`, `org.display_name`
- Workflow diff on the feature branch

## Parent actions

1. Run `worker launch-packet --state "{state_path}"`; launch `Task(subagent_type=devops-builder)` with its exact prompt, then complete from `craft_staging_path` and `launch_id`.
2. An empty workflow diff is a valid result: record `report: received` and let the human approve.
3. Present `MajorBumpCandidates` as a per-action decision, not a bulk yes/no.
4. Record `steps.implement.devops_review.report=received`, then resolve the gate with `gate resolve`.

## State keys this step owns

- `steps.implement.devops_review.status`
- `steps.implement.devops_review.report`
- `steps.implement.devops_review.approved`

## Gate

`human_approval` (`approve_devops`). Blocks `implement.documentation`, `deliver.gate`, and `deliver.ship`.

## Invalid transitions

- Post-PR CI failure triage is a different job (`devops-builder` `investigate`) and has no step of its own; it runs as rework after `deliver.ship`.
- When workflows change again during `implement.pre_pr_review`, come back here via `--decision workflows_changed` rather than approving stale evidence.
