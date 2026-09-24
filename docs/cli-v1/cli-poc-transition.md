# PoC CLI transition reference

Status: **reference only — not normative for v1**

This document maps commands from the PoC `foundry.py` CLI (`kwiktrip/.github-private-eval-foundry-approach`) to the proposed v1 capability surface. v1 behavior is defined by [cli.md](cli.md), per-group `cli-*.md` specs, and [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml). Do not implement v1 from this file alone.

---

## Why v1 replaced step-target `transition` with visit transition + engine routing

The PoC CLI used `foundry transition --to <step_id>` as the primary routing mechanism: stewards chose the next step explicitly, and the engine validated the target against flow rules and gate state.

v1 separates concerns per [visits-lifecycle.md](../workflow-schema-v1/visits-lifecycle.md) and [engine.md](../workflow-schema-v1/engine.md):

1. **Stewards request close** via `foundry visit transition` (capability id `transition`), not a destination step. They produce artifacts and receipts while the visit is `opened`.
2. **The engine seals** the visit after `on_seal` checks pass, appends `visit.sealed`, and **selects exactly one eligible connection** from the registry ([graph.md](../workflow-schema-v1/graph.md#selection)).
3. **User gates** record a decision (`foundry gate decide`); routing follows connection `on.decisions` selectors, not `--to`. Engine gates (`decider: engine`) record `gate.resolved` without that command.
4. **Checks** observe reality at hooks ([control-plane.md](../workflow-schema-v1/control-plane.md)); they do not mutate state or pick routes.

This makes the ledger authoritative: auditors reconstruct *why* a run moved by reading `check.recorded`, `gate.resolved`, `visit.sealed`, and `connection.taken` events ([run-record.md](../workflow-schema-v1/run-record.md)), rather than inferring intent from a steward-supplied step id.

---

## PoC command → v1 equivalent

| PoC command | v1 equivalent | Semantic notes |
|---|---|---|
| `run init` | `foundry run create` | Admits entry visit (`shape.intake`); initializes ledger + state. No PoC `run-mode: analysis`. |
| `run show` / `run context` | `foundry run show` / `foundry run context` | Resume packets; v1 is visit-centric. |
| `run list` / `run latest` | — | PoC operator surface. No v1 subcommand in [cli-run.md](cli-run.md). |
| `run handoff` / `run resume-packet` | `foundry run handoff` / `foundry run resume` | Handoff writes the resume packet; resume rebuilds from the ledger. |
| `run integrity-check` | `foundry run integrity-check` | Eval harness; v1 checks align to visit lifecycle events. |
| `run abandon` / `run recover` | `foundry run abandon` / `foundry run recover` | Operator halt and explicit resume. |
| `run block` | — | No v1 subcommand in [cli-run.md](cli-run.md). |
| `transition --to <step>` | `foundry visit transition` + engine seal + `connection.taken` | **No `--to`.** Steward requests close; engine routes via registry connections. |
| `transition --set KEY=JSON` | `foundry visit state patch` | State writes constrained by `allow.state` per node. |
| `gate resolve --decision` | `foundry gate decide --decision` | Gate decisions only; does not advance workflow alone. |
| `flow orchestrator-packet` | `foundry run context` + step `instructions` | No separate orchestrator packet command; steward context from engine. |
| `flow resume-packet` | `foundry run resume` | Merged into run resume surface. |
| `flow current` / `flow next` | `foundry run show` | Position derived from active visit + last sealed visit. |
| `flow validate` | `foundry flow validate` | Semantic graph validation ([cli-registry.md](cli-registry.md)). |
| `flow diagram` | `foundry flow diagram` | Diagram drift CI. |
| `observability …` / `observability subagent complete` | Ledger events + `foundry receipt seal` | Subagent launch/complete as `receipt.linked` / dedicated ledger types; no separate observability CLI group in v1. |
| `worker complete-item` | `foundry receipt seal` | Receipt is engine evidence. Which command creates the accountability commit is open; see [gaps.md](gaps.md). |
| `worker launch-packet` / `builder-packet` | Steward subagent launch (plugin) + `reads` context | Packets are engine-assembled from registry, not PoC packet commands. |
| `worker next-builder` | `foundry build build` (next ready item) | Graph-ready selection internal to build command. |
| `build` (top-level) | `foundry build build` | Grouped under `build`. Commit ownership is open; see [gaps.md](gaps.md). |
| `test` (top-level) | `foundry build test` | Manifest verification from `.foundry/app.yaml`. |
| `build-step verify` | `foundry build validate-exit` | Exit validation before `execute.build` seals. |
| `graph validate` | `foundry graph validate` | Execution graph schema validation. |
| `graph ready` | Internal to `foundry build build` | Ready-item selection not a separate operator command. |
| `app discover` / `app init` / `app validate` | `foundry app discover` / `init` / `validate` | v1 drops `run-mode: analysis`; no `documentation` section. |
| `git default-branch` | `foundry git default-branch` | Same probe; `workspace:` path roots. |
| *(no PoC equivalent)* | `foundry git clean-check` | **New** v1 probe: tracked + untracked clean per [v1-spec.md](../v1-spec.md#git-cleanliness). |
| `branch create` / `branch-name` | `foundry branch create` / `foundry branch name` | Feature branch per run; no `issue_key` required in v1. |
| `schema validate` | `foundry schema validate` | Registry schema paths unchanged. |
| `cli resolve` | `foundry cli resolve` | Capability id → argv; v1 ids use dot notation (`app.validate`). |
| `config get` | Manifest + `foundry run context` | No user-level profile store in v1. |
| `intake validate-ac` | Shape record + `approved-ac-recorded` check | AC freeze at `shape.record`, not separate intake command. |
| `delivery-check` | — | **Not in v1**; `deliver.stub` terminal only. |
| `deliver prepare` / `draft-scope-comment` / `pr-verify` | — | **Not in v1** (deliver phase deferred). |
| `jira format-board` / `format-comment` | — | **Not in v1** (Jira intake cut). |
| `risk-tier suggest` | — | **Not in v1** (`risk_tier` dropped from graph schema). |
| `prd-sync` / documentation writers | — | **Not in v1** (docs step and specialized builders cut). |
| `external-operation record` | — | **Not in v1** (GitHub/Jira external ops deferred). |
| `metrics classify` / `compare-runs` | Eval harness (`foundry run integrity-check`) | Metrics CLI not ported; harness subsumes core integrity checks. |
| `issue-key parse` / `pr-title` | — | **Not in v1** (no PR/deliver flow). |
| `project-context` | `foundry run context` | Merged into run context. |
| `invoke render` | Plugin prompt rendering | Not engine CLI in v1. |

---

## Related v1 documents

- [cli.md](cli.md) — v1 CLI hub
- [visits-lifecycle.md](../workflow-schema-v1/visits-lifecycle.md) — close vs seal
- [engine.md](../workflow-schema-v1/engine.md) — routing procedure
- [v1-spec.md](../v1-spec.md) — product scope and cuts
