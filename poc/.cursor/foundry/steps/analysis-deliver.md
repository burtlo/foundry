---
step_id: analysis.deliver
title: Deliver analysis and transition the ticket
subagent: null
run_modes: [analysis]
delivery_gate: false
state_keys:
  - steps.analysis.deliver.status
  - steps.analysis.deliver.gate_decision
---

## Purpose

Hand the analysis back: summarise what was produced, where it lives, and move the ticket to the configured review status. Terminal step of the analysis flow.

## Inputs (from parent)

- Approved report, `page_url`, `created_issue_keys`
- FactoryConfig slice: `jira_transitions`, `issue_key`

## Parent actions

1. Summarise the deliverables: report location, Confluence URL if published, follow-up issue keys.
2. When `ticket_source == jira`, prepare and reconcile the Jira transition
   before calling it. Record the successful transition ID; local/chat runs make
   no Atlassian call.

```foundry-invoke
external-operation prepare --state "{state_path}" --integration jira --operation transition_issue --target "{issue_key}" --request-json "{request_json}"
```
3. Collect confirmation and resolve the gate:

```foundry-invoke
gate resolve --state "{state_path}" --config "{config_path}" --source human --decision approve
```

4. Write the required handoff and resume in a fresh steward session.
5. Close the run and finalize its learning record:

```foundry-invoke
run complete --state "{state_path}" --config "{config_path}"
```

## Launch packet (pass to Task; not parent work)

None.

## State keys this step owns

- `steps.analysis.deliver.status`
- `steps.analysis.deliver.gate_decision`

## Gate

`human_confirm` (`confirm_analysis_complete`).

## Invalid transitions

- No branch, no commit, no PR — `implement.*` and `deliver.ship` do not exist in this flow, so `transition` cannot reach them.
- The status transition is the hand-off. Do not add a summary comment to the ticket.
