---
step_id: analysis.follow_up_create
title: Create follow-up Jira issues
subagent: null
run_modes: [analysis]
delivery_gate: false
state_keys:
  - steps.analysis.follow_up_create.status
  - steps.analysis.follow_up_create.created_issue_keys
---

## Purpose

Create the approved drafts in Jira and capture the resulting keys so the Confluence page and the final hand-off can reference them.

## Inputs (from parent)

- Approved drafts from `analysis.follow_up_draft`
- FactoryConfig slice: `jira`, `org.required_labels`

## Parent actions

1. For each approved draft, run `external-operation prepare` with the complete
   Jira create payload as `--request-json`.
2. Reconcile its `operation_id` before retrying. Only when no matching remote
   issue exists, call `createJiraIssue`, apply `org.required_labels`, and link it
   to the parent with an independently prepared `createIssueLink` operation.
3. Record each successful write with its remote key/ID, then record the keys in
   `steps.analysis.follow_up_create.created_issue_keys`.
4. Present the created keys with their URLs for confirmation.

```foundry-invoke
external-operation prepare --state "{state_path}" --integration jira --operation create_issue --target "{issue_key}" --request-json "{request_json}"
```

## Launch packet (pass to Task; not parent work)

None. Atlassian writes belong to the parent.

## State keys this step owns

- `steps.analysis.follow_up_create.status`
- `steps.analysis.follow_up_create.created_issue_keys`

## Gate

`human_confirm` (`confirm_follow_up_created`).

## Invalid transitions

- Create only what was approved. New items discovered while creating go back through `analysis.follow_up_draft`.
- Creating an issue is not the same as commenting on one; still no Jira comments on this flow.
