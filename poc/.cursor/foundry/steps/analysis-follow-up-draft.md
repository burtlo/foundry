---
step_id: analysis.follow_up_draft
title: Draft follow-up stories
subagent: story-writer
run_modes: [analysis]
delivery_gate: false
state_keys:
  - steps.analysis.follow_up_draft.status
  - steps.analysis.follow_up_draft.approved
  - steps.analysis.follow_up_draft.human_approved
  - steps.analysis.follow_up_draft.gate_decision
---

## Purpose

Convert the report's proposed follow-up work into ticket drafts the human can approve as a batch, before anything is created in Jira.

## Inputs (from parent)

- Proposed follow-up work from `analysis.research` and `analysis.report`
- FactoryConfig slice: `jira.project_key`, `org.required_labels`, `analysis.follow_up_stories`

## Parent actions

1. Run `worker launch-packet --state "{state_path}"`; launch `Task(subagent_type=story-writer)` with its exact prompt, then complete from `craft_staging_path` and `launch_id`.
2. Present every draft in full: summary, description, acceptance criteria, labels, and issue type.
3. Collect `approve` or `decline`. On `decline` the run routes to `analysis.confluence` or `analysis.deliver`.

## State keys this step owns

- `steps.analysis.follow_up_draft.status`
- `steps.analysis.follow_up_draft.approved`
- `steps.analysis.follow_up_draft.gate_decision`

## Gate

`human_approval` (`approve_follow_up_drafts`). Blocks `analysis.follow_up_create`.

## Invalid transitions

- Nothing is created in Jira at this step. Creation is `analysis.follow_up_create`.
- Skipped entirely when `config.analysis.follow_up_stories.enabled` is false, or when the research found no follow-up work.
