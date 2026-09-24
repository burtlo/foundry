# Worker launch contract

Thin execution context for Foundry (and any parent that opts in). Agent markdown under `.cursor/agents/` stays **craft + modes + output shape**. This file is the **workflow telemetry** layer.

## Split

| Lives in agent `.md` | Lives in launch packet / this contract |
|----------------------|----------------------------------------|
| Purpose, modes, craft do/don't | `FactoryConfig` role slice, `{app_folder}` |
| Human-readable Output format | Work-item / AC / dependency summaries |
| Optional craft field mapping | `craft_staging_path` when Foundry observability is on |
| | Named run-dir write paths (`brief.md`, `execution-graph.json`) |
| | Step ids for `recommended_next_state` (Foundry only) |

## Standalone vs Foundry

1. **No `craft_staging_path` in the launch prompt** — return the agent's Output format sections only. Do not invent receipts or Foundry step ids.
2. **`craft_staging_path` present** — write protocol `2.2.0` craft JSON only to
   that path. There is no mutable identity scaffold. The engine owns
   receipt/run/launch/step/agent/mode identity, input digests, and packet
   utilization in the adjacent `.meta.json`, validates provenance and
   state-patch ownership, then creates the durable receipt. Final reply is only
   the craft path.

## Parent (steward) rules

- Run `worker launch-packet --state "{state_path}"` (plus `--work-item` for builders) and pass its exact `prompt`, bounded `config`, and `inputs` to Task.
- Do **not** author `{run_dir}/brief.md` or `{run_dir}/execution-graph.json`; the planner (or named worker) writes those paths when the packet names them.
- Do **not** Write/StrReplace under `{run_dir}/receipts/`, `.meta.json`, or any path absent from `allowed_writes`. On worker Write failure: `run block` — never backfill receipts.
- Obey `steward_allowlist` from `flow orchestrator-packet` (argv prefixes + path roles).
- Gate advancement and CLI verify/validate stay on the parent/engine—not in agent craft text.

## Handoff identity contract

- Record the current host-provided conversation ID with `cursor session-record`
  after run creation/resume and before launching a worker.
- After worker completion, `run handoff` retains the stop obligation until a
  later host-provided ID is recorded.
- When a source ID exists, only a different ID fulfills the obligation. When
  the source ID was unavailable, the first non-empty ID after handoff fulfills
  it as recovery; this does not prove that the host opened a fresh conversation.
- Never invent a conversation ID to clear an obligation.

## Planner artifact paths

| Mode | Worker may Write |
|------|------------------|
| `brief` | `{run_dir}/brief.md` only (path from packet) |
| `plan` | `{run_dir}/execution-graph.json` only (path from packet) |

App source remains read-only for planner.
