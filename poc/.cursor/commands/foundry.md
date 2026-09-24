---
name: foundry
description: Software Factory — durable, registry-driven state machine for feature and analysis work
---

# Foundry (Software Factory)

Runs feature and analysis work as a **state machine** instead of a prose checklist. Step order, human gates, and skip rules live in `factory-flow.yaml`; `foundry.py` enforces them and writes durable per-run state.

Follow the skill: `@.cursor/skills/foundry/SKILL.md`

## Prerequisites

- Foundry plugin (or this repo in the workspace) plus **one app repo**
- App repo `.foundry/app.yaml` (create with `/foundry-app-bootstrap` if missing)
- For Jira intake: Atlassian Cursor plugin, HTTP MCP fallback, or a manual Jira URL — see `@.cursor/foundry/docs/atlassian-integration.md`
- For local-ticket MVP (no Jira): markdown tickets under the profile `intake.tickets_root` (see merge plan)
- `pip install -r .cursor/foundry/cli/requirements.txt`

## How to run

```text
Use foundry. Pick from the Jira board.
```

```text
Use foundry for TICKET-1234 on your-app.
```

```text
Use foundry with profile local-markdown. Pick from local tickets.
```

```text
Use foundry. Load ticket AUTH-001.
```

```text
Use foundry.

Feature: [one sentence]
Area: [service or folder]
```

## What you get

| Artifact | Location |
|----------|----------|
| Run state | `{app_folder}/.foundry/runs/{run_id}/state.json` |
| Audit log | `{app_folder}/.foundry/runs/{run_id}/events.jsonl` |
| Subagent receipts | `{app_folder}/.foundry/runs/{run_id}/receipts/` |
| Execution graph | `{app_folder}/.foundry/runs/{run_id}/execution-graph.json` |

Run artifacts are gitignored and live next to the app being edited.

## Flows

**Implementation** — intake, story refinement (two-turn AC gate), grilling, research, brief, execution graph, branch, build, validate, **code review, devops review, pre-PR review, documentation**, delivery gate, scope comment, ship.

**Analysis** — shared intake, deep-dive research, report draft, optional follow-up stories, optional Confluence publication, ticket transition. No branch, no PR, no Jira comment.

Diagram: `@.cursor/foundry/flows/factory-flow.generated.mmd`

## CLI

The orchestrator uses **`foundry-invoke` fences** (argv tail) plus **`foundry_cli`** from CLI JSON. See the skill's run context contract.

```text
python .cursor/foundry/cli/foundry.py cli resolve --factory-root <repo-or-plugin-root>
```

```foundry-invoke
run init --app-folder <path> --issue-key <KEY> --run-mode implementation
```

```foundry-invoke
flow orchestrator-packet --state <state.json> --config <config.json>
```

`flow orchestrator-packet` returns `next_invocations` (structured) and `next_commands` (rendered shell). Lint step units with `docs validate-invokes`.

## Contributing to the flow

Edit `factory-flow.yaml` and the matching `steps/*.md` together — `flow validate` fails when a unit's frontmatter disagrees with the registry on `step_id`, `subagent`, `delivery_gate`, or `state_keys`. Regenerate the diagram with `flow diagram`; CI checks it is not stale.
