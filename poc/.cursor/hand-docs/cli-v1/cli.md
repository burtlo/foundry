# CLI capability surface

Status: **draft capability spec**

The Foundry CLI is the engine surface for visit lifecycle, ledger persistence, check probes, and steward capabilities. It is how stewards request close, publish artifacts, attach receipts, resolve gates, and how the engine evaluates checks and routes connections.

**Product bindings:** locked v1 profile in [`../v1-spec.md`](../v1-spec.md). Workflow meaning in [README.md](../workflow-schema-v1/README.md).

**This document describes the proposed v1 CLI. It is not implemented yet.**

PoC migration notes live only in [cli-poc-transition.md](cli-poc-transition.md). Do not treat PoC command names as normative here.

---

## Purpose

The CLI exposes four responsibilities that mirror the workflow schema:

| Responsibility | Primary CLI groups |
|---|---|
| Run lifecycle and resume | [cli-run.md](cli-run.md) |
| Visit lifecycle (steward close) | [cli-visit.md](cli-visit.md) |
| Ledger inspection | [cli-ledger.md](cli-ledger.md) |
| Check probes (read-only) | [cli-check.md](cli-check.md) |
| Gate decisions | [cli-gate.md](cli-gate.md) |
| Artifact publication | [cli-artifact.md](cli-artifact.md) |
| Receipt evidence | [cli-receipt.md](cli-receipt.md) |
| Escalation resolution | [cli-escalation.md](cli-escalation.md) |
| App manifest and registry | [cli-app.md](cli-app.md), [cli-registry.md](cli-registry.md) |
| Workspace git and branch | [cli-git.md](cli-git.md), [cli-branch.md](cli-branch.md) |
| Execution graph and build | [cli-graph.md](cli-graph.md), [cli-build.md](cli-build.md) |

Stewards invoke only capability ids listed in the active node's `allow.cli`. The engine invokes checks, selects connections, and records gate decisions for `decider: engine` gates without steward action.

---

## Relationship to workflow schema

| Schema doc | CLI role |
|---|---|
| [engine.md](../workflow-schema-v1/engine.md) | Procedure the CLI implements: admit, hooks, seal, route |
| [visits-lifecycle.md](../workflow-schema-v1/visits-lifecycle.md) | `foundry visit transition` requests `opened → closed`; engine runs `on_close` / `on_seal` |
| [run-record.md](../workflow-schema-v1/run-record.md) | Every mutating command appends ledger events; response includes `ledger_seq` |
| [control-plane.md](../workflow-schema-v1/control-plane.md) | `foundry check eval` probes evaluate; policies decide; actions mutate visit or run |
| [artifacts.md](../workflow-schema-v1/artifacts.md) | `foundry artifact publish` appends `artifact.linked` |
| [capabilities.md](../workflow-schema-v1/capabilities.md) | `allow.cli` lists permitted capability ids per node |
| [graph.md](../workflow-schema-v1/graph.md) | After seal, engine selects one connection and appends `connection.taken` |

Governing contract (same as [README.md](../workflow-schema-v1/README.md)):

```text
Checks evaluate reality.
Policies decide what to do.
Stewards work in opened.
Visit transition requests close.
Engine routes via connections.
```

Checks never mutate state. Policies map check results to actions (`continue`, `reopen`, `halt`, `escalate`, `skip`, `disqualify`, `satisfy`). Stewards produce work and evidence while `lifecycle == opened`. A visit transition is a close request, not routing. Routing happens only after seal via connection selection.

---

## Global conventions

### Invocation

```bash
foundry <group> <subcommand> [flags]
```

In the Cursor plugin the executable is `foundry.py`; examples use the `foundry` prog name. Groups and subcommands are stable capability namespaces; individual check probes use catalog ids (see [cli-check.md](cli-check.md)).

### Global flags

| Flag | Meaning |
|---|---|
| `--workspace` | Application repository root (default: current directory) |
| `--run` | Run identifier; default: active run for the workspace |
| `--run-dir` | Run directory; overrides derivation from `--run` |
| `--registry` | Flow bundle root (default: plugin `.cursor/foundry`) |
| `--flow` | Flow id within the registry (default: `implementation`) |
| `--json` | Emit the JSON response envelope (text is the default in a terminal) |
| `--dry-run` | Validate inputs and print intended ledger events without appending |

Group specs use these names. Mutating commands require a resolvable run (`--run` or `--run-dir`). Check probes may run outside an active visit when the catalog body does not need visit scope.

### Standard JSON response envelope

Successful mutating commands return:

```json
{
  "ok": true,
  "run_id": "porcelain-0007",
  "status": "running",
  "visit": {
    "id": "v-012",
    "node_id": "execute.build",
    "lifecycle": "opened"
  },
  "ledger_seq": 84,
  "events_appended": [
    "check.recorded",
    "policy.applied",
    "lifecycle.changed",
    "visit.sealed",
    "connection.taken",
    "visit.admitted",
    "lifecycle.changed"
  ],
  "next": {
    "node_id": "execute.test",
    "visit_id": "v-013",
    "lifecycle": "examined"
  }
}
```

| Field | Meaning |
|---|---|
| `ok` | Command completed without CLI-level error |
| `run_id` | Durable run identifier |
| `status` | One of `running`, `paused`, `halted`, `definition_error`, `execution_error`, `completed` ([run-record.md](../workflow-schema-v1/run-record.md)) |
| `visit` | Active or affected visit after the command |
| `ledger_seq` | Sequence number of the last appended event |
| `events_appended` | Event types appended in order (full payloads in ledger) |
| `next` | Present when routing created a new visit; omitted when run paused, halted, or awaiting steward |

Errors return `"ok": false` with `error` (code, message) and unchanged `ledger_seq` when no events were appended.

### Check probe exit codes

From [control-plane.md](../workflow-schema-v1/control-plane.md#checks), command-bodied checks map probe exit codes to results:

| Exit code | Check result |
|:---:|---|
| `0` | `pass` |
| `1` | `fail` |
| `2` | `not_applicable` |

Any other exit, timeout, or start failure is a check evaluation error (`check.errored`, run → `execution_error`), not a policy input.

Example probe:

```bash
foundry check eval --check validate-manifest --workspace /path/to/app --json
echo $?   # 0 pass, 1 fail, 2 not_applicable
```

### Capability ids

Stewards may invoke only ids listed under `allow.cli` for the active node ([capabilities.md](../workflow-schema-v1/capabilities.md)). Common ids in the `implementation` flow:

| Capability id | Argv | Typical use |
|---|---|---|
| `transition` | `foundry visit transition` | Steward close request |
| `artifact.publish` | `foundry artifact publish` | Publish a declared artifact |
| `app.validate` | `foundry app validate` | Manifest validation; catalog check id `validate-manifest`, command body `validate_manifest` |
| `receipt.link` | `foundry receipt seal` | Attach evidence; ledger type remains `receipt.linked` |
| `git.clean` | `foundry git clean-check` | Clean-tree probe |
| `branch.create` | `foundry branch create` | Feature branch creation |
| `build.build` | `foundry build build` | One execution-graph work item |
| `build.test` | `foundry build test` | Manifest verification suite |

Catalog check ids are kebab-case (`validate-manifest`). Command bodies inside the catalog are snake_case (`validate_manifest`). They name the same probe; they are not a second CLI. See [cli-check.md](cli-check.md). Execution-graph publication uses `artifact.publish` plus [cli-graph.md](cli-graph.md) `validate` and `ensure-reference`.

Gate nodes default to `allow.cli: []`. User gates use [cli-gate.md](cli-gate.md) through `allow.user.decide`, not a separate CLI capability on the gate node.

---

## Command index

| Document | Group | Scope |
|---|---|---|
| [cli-run.md](cli-run.md) | `foundry run` | Create, show, resume, handoff, integrity |
| [cli-ledger.md](cli-ledger.md) | `foundry ledger` | Tail and query append-only events |
| [cli-visit.md](cli-visit.md) | `foundry visit` | Show visit; **`transition`** close request |
| [cli-gate.md](cli-gate.md) | `foundry gate` | Present options; record decisions |
| [cli-artifact.md](cli-artifact.md) | `foundry artifact` | Publish declared outputs |
| [cli-receipt.md](cli-receipt.md) | `foundry receipt` | Link worker evidence |
| [cli-escalation.md](cli-escalation.md) | `foundry escalation` | Resolve paused runs |
| [cli-app.md](cli-app.md) | `foundry app` | Manifest validate and bootstrap helpers |
| [cli-git.md](cli-git.md) | `foundry git` | Read-only git probes |
| [cli-branch.md](cli-branch.md) | `foundry branch` | Feature branch lifecycle |
| [cli-graph.md](cli-graph.md) | `foundry graph` | Validate the execution graph and ensure its run reference |
| [cli-build.md](cli-build.md) | `foundry build` | Build and verification runners |
| [cli-check.md](cli-check.md) | `foundry check` | Catalog check probes |
| [cli-registry.md](cli-registry.md) | `flow`, `schema`, `registry`, `cli` | Authoring and bundle introspection |

PoC-to-v1 command mapping: [cli-poc-transition.md](cli-poc-transition.md) (reference only).

**Flow walkthrough:** [cli-walkthrough.md](cli-walkthrough.md) — happy path (27 visits) and rework/failure paths with per-visit CLI spec links and `ledger show` output.

---

## Open questions

Naming that this hub used to leave open is aligned with the group specs: `foundry run create`, `foundry run show`, `foundry check eval`, `foundry receipt seal` (capability `receipt.link`), `foundry visit transition` (capability `transition`). Catalog check ids are kebab-case; command bodies are snake_case.

Remaining design gaps are in [gaps.md](gaps.md).

1. **State snapshot vs ledger authority.** [run-record.md](../workflow-schema-v1/run-record.md) states the ledger is authoritative and the snapshot is a resume aid, but `factory-run-state.schema.json` still exposes `current_step` (PoC-shaped). Unclear whether `run show` reads the snapshot, the ledger tail, or both.

2. **Engine gate audit.** `decider: engine` gates append `gate.presented` and `gate.resolved` without `foundry gate decide`. Whether those events use the same payload as user gates is unspecified.

3. **`execute.branch` capabilities.** The node has no `allow.cli` entries beyond the step default `transition`, yet branch creation mutates git. Either the engine creates the branch during transition, or `allow.cli` lists `branch.create`.

4. **Builder commits on `execute.build`.** [v1-spec.md](../v1-spec.md) says `visit transition` performs the commit. [cli-build.md](cli-build.md) says `build build` performs it, and [cli-visit.md](cli-visit.md) also has `--commit`. One owner is required.

5. **`verify.code_quality` skip vs short-circuit.** Acceptance failure should skip quality and review ([v1-spec.md](../v1-spec.md)). Routing is only via `verify.acceptance.gate` decisions. Confirm the engine never admits `verify.code_quality` or `verify.code_review` unless acceptance passed.

6. **`reverify-within-limit` counts sealed `verify.intake` visits**, not `connection.taken` events ([control-plane.md](../workflow-schema-v1/control-plane.md)). `run show` should expose that count; the display format is undefined.

7. **Dry-run semantics.** `--dry-run` is declared here. Whether it executes check probes that read the workspace or git is unresolved.

8. **Receipt link before transition.** [run-record.md](../workflow-schema-v1/run-record.md) requires `receipt.linked` before the close request it supports. Whether `transition` rejects a missing receipt or seals one from a declared path is unresolved. [cli-walkthrough.md](cli-walkthrough.md) assumes the steward already called `receipt seal`.

9. **Terminal `deliver.stub`.** The step default `allow.cli` includes `transition`. Confirm a terminal seal requires an explicit transition, or the engine seals an empty terminal step.

10. **Plugin vs standalone CLI.** `/craft-*` wraps the same engine. The error envelope and flag names (`--workspace`, `--run`, `--json`) must match `foundry.py`.

11. **Steward probes vs `allow.cli`.** [cli-walkthrough.md](cli-walkthrough.md) shows stewards running `app validate`, `git clean-check`, and `build test` on nodes whose registry `allow.cli` does not list those ids. Either those calls are engine checks only, or the registry allow lists change.
