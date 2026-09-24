---
step_id: intake.local
title: Local markdown ticket intake
subagent: null
run_modes: [implementation, analysis]
delivery_gate: false
state_keys:
  - steps.intake.local.status
  - issue_key
  - app_folder
  - developer_first_name
  - ticket_source
---

## Purpose

Load a feature or analysis ticket from a local markdown file (no Atlassian calls). Filename stem is the ticket id and becomes `issue_key`.

## Inputs (from parent)

- FactoryConfig slice: `intake`, `workspace`, `story_writer`
- Human input: ticket id, pick number, or path under `intake.tickets_root`

## Parent actions

0. If `{run_dir}/ticket.json` already exists (sealed at `run init` via `--ticket-file` / `--ticket-stdin`), skip list/pick — use sealed `id` / `title` and transition to `intake.pivot`.
1. Otherwise resolve tickets root (default `{app_folder}/tickets`):

```foundry-invoke
ticket list --app-folder "{app_folder}" --tickets-root "{intake.tickets_root}"
```

Without a direct id, show the numbered list (or `ticket pick` markdown) and **stop** for the human to choose. Do not call Jira/MCP. Do not invent ticket files unless the human asked `ticket save`.

2. Load or ingest the ticket:

```foundry-invoke
ticket load --file "{tickets_root}/{id}.md"
```

or

```foundry-invoke
ticket pick --app-folder "{app_folder}" --tickets-root "{intake.tickets_root}" --selection {n_or_id}
```

or paste:

```foundry-invoke
ticket ingest --stdin --source paste
```

3. Resolve `{app_folder}`: ticket `app` / `app_hint`, then the single app repo in the workspace, then `workspace.default_app_folder`.
4. Resolve `developer_first_name` from git config or ask once.
5. Record `--set issue_key=<stem> --set ticket_source=local` (or `paste`), transition to `intake.pivot`.

## Launch packet (pass to Task; not parent work)

None. The parent owns local file reads via CLI.

## State keys this step owns

- `steps.intake.local.status`
- `issue_key`
- `app_folder`
- `developer_first_name`
- `ticket_source`

## Gate

None. Skipped when `config.intake.source != 'local'`.

## Invalid transitions

- Do not call Atlassian tools on this path.
- Do not invent a Jira key; the markdown stem is the id.
- Do not create a branch or edit code before plan gates.
