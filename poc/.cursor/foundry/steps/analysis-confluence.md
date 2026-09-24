---
step_id: analysis.confluence
title: Publish the report to Confluence
subagent: null
run_modes: [analysis]
delivery_gate: false
state_keys:
  - steps.analysis.confluence.status
  - steps.analysis.confluence.approved
  - steps.analysis.confluence.human_approved
  - steps.analysis.confluence.page_url
---

## Purpose

Publish the approved report to the configured Confluence space, with any created follow-up keys merged into the body. Skipped when `config.analysis.confluence.enabled` is false.

## Inputs (from parent)

- Approved report from `analysis.report`
- `created_issue_keys` from `analysis.follow_up_create` when that step ran
- FactoryConfig slice: `analysis.confluence` (space key, parent page, title pattern)

## Parent actions

1. Merge the created follow-up keys into the report body.
2. Present the final page body, target space, and parent page. Collect `approve`, `retry`, or `skip`.
3. Prepare an external operation from the complete approved page payload.
   Reconcile its `operation_id` before retrying.
4. If reconciliation finds no page, call `createConfluencePage` (or
   `updateConfluencePage` when the page exists), then record the remote page ID
   and `page_url`.
5. On failure, present the error and re-offer `retry` or `skip`. Do not silently continue.

```foundry-invoke
external-operation prepare --state "{state_path}" --integration confluence --operation publish_page --target "{page_target}" --request-json "{request_json}"
```

## Launch packet (pass to Task; not parent work)

None.

## State keys this step owns

- `steps.analysis.confluence.status`
- `steps.analysis.confluence.approved`
- `steps.analysis.confluence.page_url`

## Gate

`human_approval` (`approve_confluence_publish`). Blocks `analysis.deliver`.

## Invalid transitions

- Approval at `analysis.report` does not carry over; this gate is required on its own.
- Do not link the Confluence page from a Jira comment. `analysis.confluence.link_in_jira_comment` is false by policy, and the flow has no comment step.
