---
step_id: analysis.research
title: Deep-dive investigation
subagent: codebase-researcher
run_modes: [analysis]
delivery_gate: false
state_keys:
  - steps.analysis.research.status
  - steps.analysis.research.approved
  - steps.analysis.research.human_approved
  - steps.analysis.research.receipt_id
  - steps.analysis.research.follow_up_needed
---

## Purpose

Answer the approved analysis questions with evidence from the codebase. Deeper and broader than `plan.research` — the report is the deliverable, not a precursor to building.

## Inputs (from parent)

- Approved deliverables checklist (`approved_ac`) and `assumptions`
- `app_folder`

## Parent actions

1. Run `worker launch-packet --state "{state_path}"`; launch `Task(subagent_type=codebase-researcher)` with its exact prompt, then complete from `craft_staging_path` and `launch_id`.
2. Parallel read-only researchers are allowed when the deliverables split cleanly by area.
3. Present the findings and collect `approve` or `deeper_research`. `deeper_research` is a self-loop.
4. Set `steps.analysis.research.follow_up_needed` from the researcher's `ProposedFollowUpWork` — it decides whether `analysis.follow_up_draft` runs.
5. Resolve the gate with `gate resolve --state "{state_path}" --config "{config_path}" --source human --decision approve`.

## State keys this step owns

- `steps.analysis.research.status`
- `steps.analysis.research.approved`
- `steps.analysis.research.receipt_id`
- `steps.analysis.research.follow_up_needed`

## Gate

`human_approval` (`approve_analysis_findings`). Blocks `analysis.report`.

## Invalid transitions

- No file edits, no branch, no PR anywhere on the analysis flow.
- Never post findings as a Jira comment. The analysis flow has no Jira-comment step.
