---
step_id: deliver.scope_comment
title: Out-of-scope Jira comment
subagent: null
run_modes: [implementation]
delivery_gate: false
state_keys:
  - steps.deliver.scope_comment.status
  - steps.deliver.scope_comment.gate_decision
---

## Purpose

Tell the ticket what the PR touches beyond its stated scope, before the PR exists. This is the **only** Jira comment the factory writes in an entire run.

## Inputs (from parent)

- `pr_extras_register`
- `issue_key`

## Parent actions

1. Auto-skip when `ticket_source != jira`, when `pr_extras_register` is empty, or when `issue_key` is null: run `gate resolve --state "{state_path}" --config "{config_path}" --source auto --decision skip`.
2. Otherwise draft the comment from the register — one line per `{path, reason}` — present the **exact text that would be posted**, and **STOP**.
3. On the **next** turn collect `post`, `edit`, or `skip`.
4. On `post`, prepare the idempotent operation using the approved text as
   `--request-json`; retain the returned `operation_id`.
5. Reconcile that operation before every retry. If it is not already remote,
   call `addCommentToJiraIssue` once, then record `status=succeeded` with the
   Jira comment ID as `--remote-id`.

```foundry-invoke
external-operation prepare --state "{state_path}" --integration jira --operation add_comment --target "{issue_key}" --request-json "{request_json}"
```

```foundry-invoke
external-operation reconcile --state "{state_path}" --integration jira --operation add_comment --target "{issue_key}" --operation-id "{operation_id}" --request-json "{request_json}" --evidence-json "{evidence_json}" --remote-id "{remote_id}"
```

## Launch packet (pass to Task; not parent work)

None. Atlassian writes belong to the parent.

## State keys this step owns

- `steps.deliver.scope_comment.status`
- `steps.deliver.scope_comment.gate_decision`

## Gate

`human_confirm` (`scope_comment`), two-turn. Blocks `deliver.ship`.

## Invalid transitions

- No other step in any flow may call `addCommentToJiraIssue`. The analysis flow has no equivalent step at all.
- `require_delivery_check: true` — the engine re-runs `delivery-check` before entering this step.
- Do not post and ask for approval in the same turn.
