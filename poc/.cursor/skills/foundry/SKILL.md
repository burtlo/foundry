---
name: foundry
description: >-
  Software Factory multi-chat steward. Durable runs under .foundry/runs with
  foundry.py and factory-flow.yaml. Intents: new, resume, administer, ship.
  Traffic-cop only — CLI + Task launches. Triggers on foundry, software factory,
  resume foundry.
disable-model-invocation: true
---

# Foundry (Software Factory)

**You are a session steward, not a marathon orchestrator.** You do not decide step order — `foundry.py` does. Delegate work to subagents; never inline their jobs. After every **worker/subagent** step or **hard gate**, run `run handoff` and stop (soft parent-only steps may chain). Do not keep going unless the human explicitly said so for soft steps only.

Local / paste tickets: `.cursor/foundry/docs/local-tickets.md`.

Print this banner before anything else:

```markdown
## Foundry environment
- OS / shell: {Windows + PowerShell | macOS/Linux + bash}
- factory_root: {path to org/plugin bundle}
- flow registry: .cursor/foundry/flows/factory-flow.yaml
- seam catalog: .cursor/foundry/docs/seam-packet-catalog.md
- diagram: .cursor/foundry/flows/factory-flow.generated.mmd
```

## Intent routing (first turn)

| Intent | When | First CLI |
|--------|------|-----------|
| **new** | Start ticket/feature work | `cli resolve` → `run init` (optional `--interaction-mode`, `--ticket-file` / `--ticket-stdin`) |
| **resume** | Continue an open run | `run latest` / `--run-id` / `@handoff.md` → `flow resume-packet` |
| **administer** | Drive graph work items manually | After graph approved (any mode) or `plan_control` |
| **ship** | Delivery only | `current_step` in `deliver.*` and delivery-check green |

**Intake source** (profile `intake.source`):

| Source | Kickoff | Step |
|--------|---------|------|
| `jira` | Pick from board / issue key | `intake.jira` |
| `local` | Pick from local tickets / paste markdown / `AUTH-001` | `intake.local` — `ticket list\|load\|pick\|ingest` |
| `chat` | Free-text feature statement | `intake.free_text` |

Local MVP profile: `.cursor/foundry/profiles/local-markdown.yaml`. Fixture: `.cursor/foundry/fixtures/tickets/AUTH-001.md`.

Auto-grill (`gate resolve --source auto`) is allowed only when `clarifying_questions_count == 0` and `grilling_unresolved_count == 0`. Open questions require a human gate. After every worker/subagent step or hard gate, `session_stop_hint` forces `run handoff` (+ `run integrity-check` when `require_integrity_check`). Soft parent-only steps may chain.

## Run context contract

| Variable | Source |
|----------|--------|
| `foundry_cli` | `cli resolve` / `run init` / `run context` / `flow orchestrator-packet` / `flow resume-packet` |
| `state_path`, `config_path`, `run_dir`, `app_folder`, `factory_root` | Same JSON |
| `task_subagent_type`, `subagent_mode` | orchestrator/resume packet |
| `steward_allowlist` | orchestrator/resume packet — **only** these argv prefixes + path roles |
| `session_stop_hint`, `gate_policy`, `valid_intents` | resume/orchestrator packet |

## Session identity bootstrap

After `run init` or `run latest` supplies `state_path`, record the current
host-provided conversation ID before doing step work:

```foundry-invoke
cursor session-record --state "{state_path}" --conversation-id "{host_conversation_id}"
```

Use only an ID supplied by the Cursor host; never invent or derive one. After
`run handoff`, a different host ID proves a fresh conversation. If the source
chat had no recorded ID, the first non-empty host ID may fulfill the handoff
obligation, but Foundry records that as recovery without claiming freshness
was proven.

**Pre-run (new only):**

```foundry-invoke
cli resolve --factory-root "{factory_root}"
```

## `foundry-invoke` fences

Argv tail only. Prepend `foundry_cli` from the latest JSON. One invocation per fence. Never put `python` / `foundry.py` / `{foundry_cli}` inside the fence.

## Allowlist / denylist

**Allowed:** Commands in `steward_allowlist.shell_argv_prefixes`, `Task` only when `steward_allowlist.task_subagent_type` is set, AskQuestion when `ask_question`, read paths in `read_paths`.

**Forbidden:** Shell outside the allowlist; `Write`/`StrReplace` under `{app_folder}` or `{run_dir}` except empty `write_paths`; writing staging identity / `receipts/`; inventing timestamps or backfilling receipts after worker failure (`run block` instead); raw `dotnet`; inventing `--to` after failed transition; loading full `events.jsonl` or all receipts into chat.

Worker craft vs telemetry: agents are craft-only; Foundry launch context is `.cursor/foundry/docs/worker-launch-contract.md`.

## Session loop (not until terminal)

1. `flow resume-packet` or `flow orchestrator-packet` — read **only** the named step unit + `steward_allowlist`.
2. One action batch for that step (subagent launch/complete or parent-only gates).
3. Auto gates: `gate resolve --source auto --decision …` **only** when `gate_policy.auto_eligible` (engine blocks auto-grill when `clarifying_questions_count > 0`).
4. Hard gates: present, wait for human, then `transition`.
5. If `session_stop_hint` is `stop_after_worker`, `stop_after_hard_gate`, or `stop_after_build_verify`:

```foundry-invoke
run handoff --state "{state_path}"
```

```foundry-invoke
run integrity-check --state "{state_path}"
```

Stop the chat. Kickoff for the next chat is in `handoff.md`.

## Intent × step (summary)

- `resume` — any open run
- `administer` — after graph approved, or at plan/build under `plan_control`
- `ship` — `deliver.*` only
- `new` — no open run / explicit new

Full matrix: `.cursor/foundry/docs/seam-packet-catalog.md`.

## Start (new)

```foundry-invoke
run init --app-folder "{app_folder}" --issue-key {issue_key} --run-mode {implementation|analysis} --factory-root "{factory_root}" --developer-first-name {name} --risk-tier {low|medium|high} --interaction-mode {interactive|drive_to_pr|plan_control}
```

If `run init` returns `APP_MANIFEST_MISSING`, stop and send the human to `/foundry-app-bootstrap`. Do not invent YAML. Do not infer commands from `AGENTS.md`, `.sln`, or Makefiles.

## Resume

```foundry-invoke
run latest --app-folder "{app_folder}" --issue-key {issue_key}
```

```foundry-invoke
flow resume-packet --state "{state_path}" --config "{config_path}"
```

If `open_subagent_launches` is non-empty: complete or `run block` — do not double-launch.

## Hard rules

- Never infer step order from prose.
- Jira comments only at `deliver.scope_comment`.
- No commit/push/`gh pr create` before `delivery-check` exit 0.
- `plan.brief` / `plan.graph`: **planner** writes `brief.md` / `execution-graph.json`; parent only launch → complete → CLI validate/record → gate.
- `implement.build`: orchestrator-only; `build-step verify` receipt only.
- After `run complete`, learning files are offline — do not load `learning_record.json` into the next steward.

## Blocked runs

```foundry-invoke
run block --state "{state_path}" --reason "{errorCode}: {message}" --step-id {current_step}
```

```foundry-invoke
run unblock --state "{state_path}" --decision "{human_note}"
```

```foundry-invoke
run abandon --state "{state_path}" --reason "{taxonomy reason}"
```

## Reference

| Thing | Path |
|-------|------|
| Seam catalog | `.cursor/foundry/docs/seam-packet-catalog.md` |
| Worker launch contract | `.cursor/foundry/docs/worker-launch-contract.md` |
| Post-run learning | `.cursor/foundry/docs/post-run-learning.md` |
| Flow registry | `.cursor/foundry/flows/factory-flow.yaml` |
| Step units | `.cursor/foundry/steps/*.md` |
