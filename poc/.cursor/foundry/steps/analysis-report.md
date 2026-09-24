---
step_id: analysis.report
title: Analysis report draft
subagent: documentation-writer
run_modes: [analysis]
delivery_gate: false
state_keys:
  - steps.analysis.report.status
  - steps.analysis.report.approved
  - steps.analysis.report.human_approved
---

## Purpose

Turn research findings into the written deliverable: an answer per approved deliverable, evidence, recommendations, and proposed follow-up work. Draft only — publication is a separate, separately gated step.

## Inputs (from parent)

- `steps.analysis.research.receipt_id` and its receipt
- `approved_ac`

## Parent actions

1. Run `worker launch-packet --state "{state_path}"`; launch `Task(subagent_type=documentation-writer)` with its exact prompt, then complete from `craft_staging_path` and `launch_id`.
2. Present the full draft in chat and collect `approve` or `report_edits`. `report_edits` is a self-loop.
3. Resolve the gate with `gate resolve --state "{state_path}" --config "{config_path}" --source human --decision approve`.

## State keys this step owns

- `steps.analysis.report.status`
- `steps.analysis.report.approved`

## Gate

`human_approval` (`approve_analysis_report`). Blocks `analysis.follow_up_draft`, `analysis.confluence`, and `analysis.deliver`.

## Invalid transitions

- Approving the draft here is not approval to publish. `analysis.confluence` has its own gate.
- The report is never a Jira comment.
