# Check lookup CLI (Path A′ — draft)

Status: **design draft** — not implemented. Complements [README.md](README.md) (POC import guide). **Path B** (no `checks[]` on workers; steward builds intake receipt from ledger) is what `intake-checker.shape` uses today. This document captures **Path A′**: thin worker inputs plus read-only CLI to inspect catalog checks and recorded results.

---

## Problem

Passing bare `checks[]` (`id` + `status`) to a subagent is rarely enough to act on a failure. Passing full `summary` + `evidence` on every spawn bloats the launch context and duplicates the ledger.

Path A′: give the worker **`visit_id` + `run_id`** (already in inputs) and optional read-only CLI to:

1. **Describe** what a catalog check is (definition, probe, hooks) — without opening `factory-flow.yaml`.
2. **Show** what the engine recorded when that check last ran on this visit — without re-running `check eval`.

---

## Two commands (proposed)

| Command | Question it answers | Mutates state? |
|---------|---------------------|----------------|
| `foundry check describe` | What is `validate-manifest` and how is it evaluated? | No |
| `foundry check show` | What did the engine record when this check ran on this visit? | No |

**Not granted to assessment workers:** `foundry check eval` — re-runs the probe against *current* reality; audit truth is `check.recorded` at hook time ([control-plane.md](../workflow-schema-v1/control-plane.md), [run-record.md](../workflow-schema-v1/run-record.md)).

---

## `foundry check describe`

Registry introspection — documentation reflective of the flow bundle, not a live run.

### Purpose

Return the catalog definition for a check id: body type (`when` | `command` | `path`), probe or expression summary, and which nodes reference it. Agents and operators use this to interpret an id like `validate-manifest` without reading YAML.

### Sample invocation

```text
foundry check describe --check validate-manifest --json
```

Optional scope when multiple flows exist:

```text
foundry check describe --check validate-manifest --flow implementation --json
```

### Sample JSON result

```json
{
  "check_id": "validate-manifest",
  "flow_id": "implementation",
  "body": "command",
  "command": "validate_manifest",
  "probe_cli": "foundry app validate",
  "description": "Validates .foundry/app.yaml against app-manifest schema and capability probes.",
  "nodes": [
    {"node_id": "shape.intake", "hook": "on_open"},
    {"node_id": "execute.intake", "hook": "on_open"},
    {"node_id": "verify.intake", "hook": "on_open"}
  ],
  "default_policies": {
    "pass": "continue",
    "fail": "halt",
    "not_applicable": "continue"
  },
  "registry_ref": "registry:flows/factory-flow.yaml#checks.validate-manifest"
}
```

For `when` checks (e.g. `approved-ac-recorded`):

```json
{
  "check_id": "approved-ac-recorded",
  "body": "when",
  "expression": "state.approved_ac_version >= 1",
  "description": "Approved acceptance criteria version is recorded in run state.",
  "nodes": [
    {"node_id": "execute.intake", "hook": "on_examine"}
  ]
}
```

### Who invokes

| Actor | When |
|-------|------|
| Worker (read contract) | Understand a check id mentioned in steward context or human message |
| Steward / operator | Debug without opening the registry |
| `foundry docs` / help surfaces | Same underlying resolver |

### Relation to existing docs

Today: [cli-check.md](../cli-v1/cli-check.md) catalog table is human-maintained. `check describe` would be **generated from** `factory-flow.yaml` `flow.checks` + node lifecycle references — single source of truth.

---

## `foundry check show`

Recorded result introspection — read the ledger payload from hook execution, not a fresh eval.

### Purpose

Return the most recent `check.recorded` event for a given check on a given visit (and run), including stored `output` from the probe or expression evaluation. Answers: “`validate-manifest` failed on `v-008` — what exactly was recorded?”

### Sample invocation

```text
foundry check show --check validate-manifest --visit v-008 --run porcelain-0007 --json
```

Shorthand when a single visit is active in context:

```text
foundry check show --check validate-manifest --visit v-008 --json
```

List all checks recorded for a visit (no `--check`):

```text
foundry check show --visit v-008 --run porcelain-0007 --json
```

### Sample JSON result (command probe, fail)

```json
{
  "source": "ledger",
  "event_type": "check.recorded",
  "seq": 77,
  "run_id": "porcelain-0007",
  "visit_id": "v-008",
  "node_id": "execute.intake",
  "hook": "on_open",
  "check_id": "validate-manifest",
  "result": "fail",
  "policy": {
    "action": "continue",
    "reason": null
  },
  "output": {
    "body": "command",
    "probe": "foundry app validate",
    "exit_code": 1,
    "stderr": "builders.routes[0].globs: must not be empty",
    "summary": "app validate exit 1: builders.routes[0].globs must not be empty"
  },
  "recorded_at": "2026-09-24T14:38:01Z"
}
```

### Sample JSON result (`when` check, fail)

```json
{
  "check_id": "approved-ac-recorded",
  "result": "fail",
  "hook": "on_examine",
  "output": {
    "body": "when",
    "expression": "state.approved_ac_version >= 1",
    "actual": {"approved_ac_version": 0},
    "summary": "approved_ac_version is 0; need >= 1"
  }
}
```

### Who invokes

| Actor | When |
|-------|------|
| Worker (Path A′ contract) | Failed check needs explanation; worker has thin `checks[]` or only `visit_id` |
| Steward | Building intake receipt `checks[].summary` / `evidence` from ledger when sealing |
| Operator | Debug after `policy.applied` continued despite `fail` |

### Prerequisites (engine)

`check.recorded` must persist rich **`output`** at hook time (same shape as `check eval` JSON today). Minimal ledger rows (`check` + `result` only) are insufficient for `check show` to add value beyond the launch packet.

---

## Path comparison

| Path | Worker gets | Worker returns | Intake receipt `checks[]` |
|------|-------------|----------------|---------------------------|
| **A (fat)** | `checks[]` with `summary` + `evidence` | Assessment only | Invoker copies from launch packet |
| **A′ (lazy)** | `visit_id`, optional thin `checks[]` | Assessment; may call `describe` / `show` | Invoker builds from ledger + worker narrative |
| **B (current)** | No `checks[]` | Assessment only | **Steward** builds from ledger when sealing |

`intake-checker.shape` uses **Path B** — see [`.cursor/agents/intake-checker.shape.md`](../../.cursor/agents/intake-checker.shape.md).

Path A′ workers would list in contract YAML, e.g.:

```yaml
read_cli:
  - check.describe
  - check.show
```

Separate from steward `allow.cli` on nodes ([capabilities.md](../workflow-schema-v1/capabilities.md)).

---

## Worker usage pattern (Path A′)

When a future worker is allowed `check.show`:

1. Inputs include `visit_id`, `run_id`, and optionally `failed_check_ids[]` (ids only).
2. For each failed id (or when findings require it): `foundry check describe --check <id>` then `foundry check show --check <id> --visit <visit_id>`.
3. Worker cites recorded `output.summary` in **Findings**; does **not** copy catalog checks into a receipt table (steward still owns intake receipt `checks[]`).

Intake-checker on Path B skips steps 1–2 for checks; it assesses `app_folder` and plan content directly.

---

## CLI surface sketch

```text
foundry check describe --check <catalog-id> [--flow <flow-id>] [--json]
foundry check show     --visit <visit-id> [--check <catalog-id>] [--run <run-id>] [--json]
foundry check eval     ...   # existing; re-run probe — NOT for workers
```

Optional future grouping under docs/help:

```text
foundry docs check describe --check validate-manifest
```

Alias of `check describe` for discoverability under a `docs` namespace; same resolver, no second source of truth.

---

## Open questions

| Item | Notes |
|------|-------|
| Rich `output` on `check.recorded` | Required for `check show`; spec gap in current ledger samples |
| `check show` without `--check` | Return all `on_examine` + `on_open` checks for visit — useful for steward sealing Path B receipts |
| Worker `read_cli` vs node `allow.cli` | Workers need explicit contract capability; must not inherit steward grants |
| Policy on `show` when `fail` + `continue` | Include `policy.applied` payload so agent knows visit opened despite fail |

---

## Related

- [cli-check.md](../cli-v1/cli-check.md) — `check eval` (live probe)
- [cli-ledger.md](../cli-v1/cli-ledger.md) — `ledger show`, `ledger query`
- [intake-receipt.schema.json](../../.cursor/foundry/schemas/intake-receipt.schema.json) — `checks[].summary`, `checks[].evidence`
- [README.md](README.md) — POC import; Path B worker rules
