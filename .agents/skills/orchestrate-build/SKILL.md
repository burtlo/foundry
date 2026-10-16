---
name: orchestrate-build
description: >-
  Orchestrate plan-bundle implementation from implementation.md or a bundle
  directory: delegate each package to plan-implementer, then independent
  plan-verifier subagents. Use with /orchestrate-build after
  /spec-implementation-map when implementation.md is ready for orchestration.
disable-model-invocation: true
---

# Orchestrate build (plan bundle)

Execute **`docs/plans/<bundle>/implementation.md`** as an **orchestrator only**: assign **one package at a time** to implementer and verifier subagents. Do **not** implement product code in the orchestrator session.

Companion agents: [plan-implementer](../../agents/plan-implementer.md), [plan-verifier](../../agents/plan-verifier.md).

## Relationship to other workflows

| Step | Command / artifact |
|------|-------------------|
| Spec | `/retro-feature-interview` → `spec.md` |
| Map | `/spec-implementation-map` → `implementation.md` |
| **Build** | **`/orchestrate-build`** → package loop + `orchestration-progress.md` |
| Engine flow | `foundry shape` / `foundry start` (separate; does not replace this skill) |

## Inputs

Resolve before any package work:

| Field | Source |
|-------|--------|
| `bundle_dir` | Directory containing `implementation.md` (e.g. `docs/plans/foundry-up/`) |
| `implementation_path` | **Or** path to `implementation.md`; derive `bundle_dir` as parent |
| `packages` | Optional — subset (`P1`, `P4`) default: all packages in build order |
| `from_package` | Optional — resume at this ID (skip earlier unless `packages` overrides) |
| `repair_limit` | Optional — max implementer re-runs after verifier `fail` (default **1**) |
| `auto_continue` | Optional — if true, proceed to next package without a user gate between packages (default **false**) |

**Required files in bundle:**

- `implementation.md` with **Orchestration packages** table and **Package briefs** + **Verifier briefs**
- `spec.md` (read AC/decisions for excerpts)

If the map is missing packages or verifier briefs, **stop** and point the operator to `/spec-implementation-map`.

## Orchestrator contract (mandatory)

Violations invalidate the run.

1. **No product implementation** — The orchestrator must **not** use Write/StrReplace/Delete on product code, tests, CLI, host, or generated docs outside the bundle progress file. Allowed writes: `docs/plans/<bundle>/orchestration-progress.md` only (unless the user explicitly asks to edit the map or README).
2. **Subagents only for packages** — Each package **must** go through:
   - **Implement:** Task → `plan-implementer` (see [Launching subagents](#launching-subagents))
   - **Verify:** separate Task → `plan-verifier` (fresh invocation, **no** `resume` from implementer)
3. **Order** — Follow **Suggested implementation order** in `implementation.md`; if absent, topological order from **Depends on** in the orchestration table. Do not start a package until all dependencies have verifier `pass` (or user waives a dependency in chat).
4. **Gates** — See [Phases](#phases). Do not skip the opening agenda gate unless the user said `skip agenda` or invoked with a single `packages` entry and explicit “run now”.
5. **Reporting** — After each package, append to `orchestration-progress.md` and present a summary in chat; if `auto_continue` is false, **stop** before the next package.

## Launching subagents

Use the **Task** tool for every implement and verify step.

1. Read [plan-implementer.md](../../agents/plan-implementer.md) or [plan-verifier.md](../../agents/plan-verifier.md) and embed the contract in the Task `prompt`.
2. Set `subagent_type` to the agent name when available: **`plan-implementer`**, **`plan-verifier`**. If the environment rejects unknown types, use **`generalPurpose`** and begin the prompt with: `You are plan-implementer` or `You are plan-verifier; readonly — do not edit files` plus the full agent file rules.
3. For **plan-verifier**, use `model: fast` when supported; verifier prompt must **not** include the implementer’s tool trace — only structured report, briefs, spec excerpt, and `git_diff_scope`.
4. `run_in_background: false` unless the user requests background.
5. Require structured JSON output per agent files; parse before continuing.

### Implementer prompt must include

- `package_id`, full **package brief** text, **spec excerpt**, paths, explicit **out of scope**
- Instruction: return JSON report only; single package

### Verifier prompt must include

- `package_id`, full **verifier brief** text, **spec excerpt**, `git_diff_scope`, implementer JSON report
- Instruction: readonly; return JSON verdict

## Phases

### 1. Resolve and ingest

- Normalize `bundle_dir` and `implementation_path`.
- Read `implementation.md` (packages table, order, briefs) and `spec.md`.
- Build ordered package list applying `from_package` / `packages`.
- If `orchestration-progress.md` exists, read for completed packages; skip those with `verdict: pass` unless user asks to re-run.

### 2. Agenda (presentation turn)

Render in chat:

- Bundle path and package queue (IDs + titles)
- Dependencies and starting package
- Gates: per-package implement → verify → optional repair → user continue (unless `auto_continue`)
- Progress file path

**Stop.** No Task launches in this turn unless the user already approved (“go”, “start P1”, `skip agenda`).

### 3. Package loop (decision / execution turns)

For each package `Pn`:

1. **Implement** — Task `plan-implementer` with frozen brief.
2. If implementer `blocked` or `failed` → record in progress, **stop** and ask operator.
3. **Verify** — Task `plan-verifier` with fresh context.
4. If `fail` and repairs remain → Task implementer again with verifier findings (same package); re-verify once.
5. If still `fail` → **stop**; do not advance to dependent packages.
6. Append **Package Pn** section to `orchestration-progress.md` (implementer summary, verifier verdict, findings).
7. Present package outcome in chat. If not `auto_continue`, **stop** before `Pn+1`.

### 4. Completion

When the queue is done or stopped:

- Summarize packages: pass / fail / skipped
- Remind operator about commit/PR policy (orchestrator does not commit unless asked per package)

## `orchestration-progress.md` template

Create or update in the bundle:

```markdown
# Orchestration progress — <bundle>

Status: **in progress** | **blocked** | **complete**

| Package | Implement | Verify | Notes |
|---------|-----------|--------|-------|
| P1 | completed | pass | … |

## Package P1

### Implementer
…

### Verifier
…
```

## Anti-patterns

- Orchestrator editing source files “to save time”
- Skipping verifier after implementer success
- Passing implementer chat history into verifier Task
- Running multiple packages in one implementer Task
- Starting `/orchestrate-build` on a draft map without orchestration packages
- Using `/spec-implementation-map` in the same session as a substitute for this skill
