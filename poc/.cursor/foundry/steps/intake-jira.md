---
step_id: intake.jira
title: Jira intake and ticket packet
subagent: null
run_modes: [implementation, analysis]
delivery_gate: false
state_keys:
  - steps.intake.jira.status
  - issue_key
  - app_folder
  - developer_first_name
  - atlassian_source
  - ticket_source
---

## Purpose

Turn a Jira board pick or a direct issue key into a ticket packet the rest of the run reads from: issue key, summary, description, acceptance criteria, issue type, labels, and the app repo the work lands in.

## Inputs (from parent)

- FactoryConfig slice: `jira`, `atlassian`, `workspace`, `org.required_labels`
- Human input: a board selection number, an issue key, or a Jira browse URL

## Parent actions

1. Resolve the Atlassian connection in fallback order: Atlassian Cursor plugin, then HTTP MCP (`user-atlassian`, call `mcp_auth` when STATUS says authentication is required), then manual browse URL. Record which one worked in `atlassian_source`.
2. Without a direct key, run `jira.pick_list_jql` with `{{project_key}}` substituted, search via MCP, then format the board deterministically:

```foundry-invoke
jira format-board --issues '{json}' --project-key {project_key} --developer-first-name {name}
```

Show the resolved JQL and the CLI markdown output, then **stop** for the human to pick. Do not ask which app repo first.
3. `getJiraIssue` on the selected key. Claim the ticket if `jira.claim_on_pick` is set.
4. `atlassianUserInfo` for `developer_first_name` (branch naming).
5. Resolve `{app_folder}`: ticket hints, then the single app repo in the workspace, then `workspace.default_app_folder`.
5. Record evidence with `ticket_source=jira` and transition.

## Launch packet (pass to Task; not parent work)

None. The parent owns Atlassian calls.

## State keys this step owns

- `steps.intake.jira.status`
- `issue_key`
- `app_folder`
- `developer_first_name`
- `atlassian_source`

## Gate

None. The step is skipped when `!config.jira.enabled`; the engine routes to `intake.free_text`.

## Invalid transitions

- Do not post a Jira comment here. The only factory comment is `deliver.scope_comment`.
- Do not create a branch or edit code before `plan.brief` and `plan.graph` are approved.
