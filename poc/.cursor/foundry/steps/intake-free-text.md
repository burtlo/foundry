---
step_id: intake.free_text
title: Free-text intake
subagent: null
run_modes: [implementation, analysis]
delivery_gate: false
state_keys:
  - steps.intake.free_text.status
  - app_folder
  - developer_first_name
  - ticket_source
---

## Purpose

Accept a feature or investigation described in **unstructured** chat when Jira is disabled or unreachable, and produce the same shape of packet `intake.jira` produces minus the issue key.

For a **structured markdown ticket** pasted into chat (frontmatter + body), use `intake.local` / `ticket ingest --stdin --source paste` instead — see [local-tickets.md](../docs/local-tickets.md) Kickoff B.

## Inputs (from parent)

- FactoryConfig slice: `workspace`, `story_writer`
- Human input: one-sentence feature statement plus the target area or service

## Parent actions

1. Confirm the feature statement and the target area with the human in one turn.
2. Resolve `{app_folder}` from the stated area, then the single app repo in the workspace, then `workspace.default_app_folder`.
3. Resolve `developer_first_name` from git config or ask once.
4. Leave `issue_key` null when no local id. Set `ticket_source=chat`. Downstream steps that need a Jira key (`deliver.scope_comment`) skip themselves.

## Launch packet (pass to Task; not parent work)

None.

## State keys this step owns

- `steps.intake.free_text.status`
- `app_folder`
- `developer_first_name`

## Gate

None. Skipped when `config.jira.enabled`.

## Invalid transitions

- Do not invent a Jira key. A null `issue_key` is valid state for this path.
