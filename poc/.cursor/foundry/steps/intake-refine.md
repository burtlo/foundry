---
step_id: intake.refine
title: Story refinement
subagent: story-writer
run_modes: [implementation, analysis]
delivery_gate: false
state_keys:
  - steps.intake.refine.status
  - steps.intake.refine.receipt_id
  - readiness
  - clarifying_questions_count
  - draft_ac
---

## Purpose

Close the gap between a thin ticket and something buildable. Story-writer returns **Readiness**, **MissingOrWeak**, draft acceptance criteria, and clarifying questions. Presentation and human approval happen at `intake.present_ac` and `intake.approve_ac`.

## Inputs (from parent)

- FactoryConfig slice: `story_writer`, `org.required_labels`, `analysis`
- Ticket packet and `issue_key` from intake
- Subagent mode: `implementation` or `analysis_deliverables`, from registry `subagent_mode`

## Parent actions

1. Launch `story-writer` with the registry's `subagent_mode` and the ticket packet. Embed FactoryConfig from `config get --role story-writer`. Use `task_subagent_type` from `flow orchestrator-packet` (must be `story-writer`, not `generalPurpose`).
2. Run `worker launch-packet --state "{state_path}"`, pass its exact prompt to Task, and complete from `craft_staging_path` plus `launch_id`. Never write under `{run_dir}/receipts/` yourself.
3. Parse the report from the completed receipt:
   - Set `readiness` to `Ready`, `Needs refinement`, or `Blocked`.
   - Set `clarifying_questions_count` from the ClarifyingQuestions list length.
   - Build `draft_ac[]` from SuggestedAcceptanceCriteria / DeliverableChecklist (each item: `{id, text, source}` with `source` of `jira` or `proposed`).
4. `transition --to intake.grill` (engine skips grill on the fast lane when `readiness == Ready` and count is 0).

## State keys this step owns

- `steps.intake.refine.status`
- `steps.intake.refine.receipt_id`
- `readiness`
- `clarifying_questions_count`
- `draft_ac`

## Gate

None on this step. The two-turn gate lives on `intake.present_ac`; scope freeze on `intake.approve_ac`.

## Invalid transitions

- Do not present AC to the human here — that is `intake.present_ac`.
- Do not launch `codebase-researcher` or builders until `intake.approve_ac` completes.
- Do not hand-write receipts or retry `subagent complete` with a fabricated receipt after `INVALID_RECEIPT`. Relaunch the subagent or `run block` and ask the human.
