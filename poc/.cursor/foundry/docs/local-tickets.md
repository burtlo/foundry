# Local markdown tickets

Offline intake for Foundry when `intake.source: local`, or when a ticket is **pasted** into the kickoff prompt. No Atlassian calls.

## Contract

| Item | Value |
|------|--------|
| Layout | `{tickets_root}/AUTH-001.md` |
| Sealed run artifact | `{run_dir}/ticket.json` (schema: `schemas/packets/ticket.schema.json`) |
| Id | Filename stem / frontmatter `id`; must appear in the body |
| Required frontmatter | `id`, `title`, `type` |
| Profile | `.cursor/foundry/profiles/local-markdown.yaml` |
| Step | `intake.local` (skips pick when `ticket.json` already sealed) |
| CLI | `ticket list` · `ticket load` · `ticket pick` · `ticket ingest` · `ticket save` |
| Fixture | `.cursor/foundry/fixtures/tickets/AUTH-001.md` |

`intake.tickets_root` defaults to `tickets` under the app folder (or an absolute path). Free-form stems are allowed (`AUTH-001`, `feat-refresh`).

## Kickoff A — local file

```text
Use foundry with profile local-markdown. Load ticket AUTH-001.
```

```foundry-invoke
run init --app-folder "{app_folder}" --issue-key AUTH-001 --run-mode implementation --factory-root "{factory_root}" --config .cursor/foundry/profiles/local-markdown.yaml --developer-first-name you --risk-tier medium --ticket-file "{app_folder}/tickets/AUTH-001.md"
```

Optional `--start-point {branch}` records the Git ref used later at `implement.branch` instead of the detected default (`main`/`master`). Use it when the feature branch must grow from the current app branch (for example `version-0.4.0`).

## Kickoff B — paste into the prompt

Paste a full markdown ticket (frontmatter + body) into the Agent chat, then:

```text
Use foundry with profile local-markdown. Ingest the pasted ticket.
```

```foundry-invoke
ticket ingest --stdin --source paste
```

or seal at init:

```foundry-invoke
run init --app-folder "{app_folder}" --run-mode implementation --factory-root "{factory_root}" --config .cursor/foundry/profiles/local-markdown.yaml --developer-first-name you --risk-tier medium --ticket-stdin
```

Optional: persist paste to disk with `ticket save --tickets-root "{app_folder}/tickets" --stdin`.

## Rules

- After seal, steps read `{run_dir}/ticket.json` only — not the live `tickets/*.md` file.
- Steward must **not** invent ticket files unless the human asked `ticket save`.
- Scope comment to Jira is skipped when `ticket_source != jira`.

## Other intake sources

| `intake.source` | When |
|----------------|------|
| `jira` | Board pick or issue key (IoT default profile) |
| `local` | Markdown tickets under `tickets_root` and/or sealed paste |
| `chat` | Free-text feature statement (no structured ticket) |
