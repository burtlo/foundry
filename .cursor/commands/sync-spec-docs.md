---
name: sync-spec-docs
description: >-
  Documentation lead after an implementation phase: updates acceptance feature files,
  runs foundry doc build, and verifies spec sync. Launches scribe then scribe-verifier.
  Use after implement/build work to align features and generated docs with the codebase.
---

# Sync spec docs

Role: documentation lead — launch **scribe**, then **scribe-verifier**, and return structured results.

## User input

Capture from the user message:

| Field | Source |
|---|---|
| `change_scope` | Git ref range (`main...HEAD`), path list, or phase name + summary (required) |
| `focus` | Optional emphasis (nodes, CLI, gates, …) |
| `phase_report_path` | Optional implementation report under `docs/` |

If the user only describes a phase verbally, combine phase name and summary into `change_scope`.

**Registry:** This command targets the **Foundry** repository (`.cursor/foundry` in workspace). If the workspace is an application repo, set `registry_root` from `.foundry/foundry.yaml` `registry` field or ask the user for the Foundry repo path.

## Procedure

1. Confirm workspace is the Foundry registry or resolve `registry_root`.
2. Optional: resolve CLI for orchestration context (application repos only):

```foundry-invoke
cli resolve
```

Scribe runs `git`, feature edits, and `doc build` via shell in the Foundry repo — not through steward run commands.

3. Launch the **scribe** subagent with the launch prompt below.
4. Return scribe's `summary_markdown` to the user in chat.
5. Launch **scribe-verifier** with scribe output and the same `git_diff_scope` as `change_scope`.
6. Return verifier `summary_markdown`. If `verdict` is `fail`, list blocker/major findings and do not treat the sync as complete.

## Scribe launch prompt

```
Sync Foundry specification and generated documentation per your agent instructions.

## Inputs

| Field | Value |
|---|---|
| registry_root | {registry_root or workspace root} |
| change_scope | {change_scope} |
| focus | {focus or "full spec sync"} |
| phase_report_path | {phase_report_path or "none"} |

## Task

Follow scribe instructions exactly: investigate changes, update acceptance features under .cursor/foundry/cli/tests/acceptance/features/, run doc build, verify output. Return full JSON including summary_markdown and verdict.
```

## Verifier launch prompt

```
Verify the Scribe pass per your agent instructions.

## Inputs

| Field | Value |
|---|---|
| registry_root | {registry_root} |
| scribe_summary | {paste scribe summary_markdown or path to saved report} |
| git_diff_scope | {same as change_scope} |

## Task

Follow scribe-verifier instructions exactly. Re-run doc build and pytest test_doc_build.py when feasible. Return full JSON including findings and verdict.
```

## Out of scope

| Action | Use when |
|---|---|
| Implementing product behavior | Builder agents / craft execute |
| Starting or continuing a steward run | `/craft-shape`, `/craft-execute` |
| Post-run steward quality review | `/evaluate-run` |
| Archiving runs | `/review-archive-run` |
| Editing generated docs by hand instead of features + `doc build` | Fix features/sources, then re-run this command |

## What good output looks like

- Scribe report with Feature Coverage, Documentation, Behavioral Discoveries, Generation, Verification, Documentation Debt
- `verdict` `pass` or `pass_with_gaps` with explicit gaps listed
- Verifier checklist all pass, or clear fail findings with evidence
- `doc build` exit code 0 confirmed by verifier

## Canonical references

- Agent: `.cursor/agents/scribe.md`
- Verifier: `.cursor/agents/scribe-verifier.md`
- CLI: [docs/cli/doc-build.md](../../docs/cli/doc-build.md)
