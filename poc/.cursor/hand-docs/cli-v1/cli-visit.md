# visit

Status: **draft capability spec**

The `foundry visit` command group inspects and mutates a single visit's lifecycle and scoped state. Visit lifecycle states, hooks, and the closed-vs-sealed distinction are defined in [visits-lifecycle.md](../workflow-schema-v1/visits-lifecycle.md). The engine runs `on_close` and `on_seal` hooks per [engine.md](../workflow-schema-v1/engine.md); `transition` requests close only and does not select routing destinations per [capabilities.md](../workflow-schema-v1/capabilities.md).

---

## show

### Purpose

Return the current visit snapshot: node id, lifecycle, outcome, decision, outputs, and routing lineage.

### Who invokes

| Actor | When |
|---|---|
| steward | Confirm visit state before `transition` |
| operator | Debug stuck or reopened visits |
| eval | Assert lifecycle and outputs |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--visit` | no | Visit id (default: active visit) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry visit show --run run-2026-09-24-porcelain-003 --visit v-009 --json
```

### Sample JSON result

```json
{
  "id": "v-009",
  "node_id": "execute.build",
  "kind": "step",
  "lifecycle": "opened",
  "outcome": null,
  "decision": null,
  "outputs": {},
  "routed_from_visit_id": "v-008",
  "routed_by_connection_id": "execute.plan-to-execute.build"
}
```

### Ledger events appended

None (read-only).

### Related factory-flow.yaml nodes/checks

Any visit; sealed example on `shape.record` with `approved-ac-recorded` on `on_seal`.

### Cross-links

- [cli-run.md](cli-run.md) — `context` for steward reads/allow
- [visits-lifecycle.md](../workflow-schema-v1/visits-lifecycle.md) — lifecycle state meanings

---

## state patch

### Purpose

Apply allowed writes to run state scoped to the active visit's capability grant. Does not change lifecycle or append routing events.

### Who invokes

| Actor | When |
|---|---|
| steward | Record domain fields during an `opened` step (e.g. `approved_ac`, `feature_branch`) |
| engine | Rejected — engine updates state only through hook side effects |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--visit` | no | Visit id (default: active visit; must be `opened`) |
| `--set` | yes* | JSON object of state paths and values (*or `--file`) |
| `--file` | no | `run:` or `workspace:` path to JSON patch document |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry visit state patch --run run-2026-09-24-porcelain-003 --set '{"approved_ac_version": 1, "nodes.shape.record.approved_at": "2026-09-24T12:00:00Z"}' --json
```

### Sample JSON result

```json
{
  "visit_id": "v-007",
  "node_id": "shape.record",
  "lifecycle": "opened",
  "patched_paths": ["approved_ac_version", "nodes.shape.record.approved_at"],
  "rejected_paths": []
}
```

### Ledger events appended

None. State snapshot updates are not duplicated in the ledger; auditors correlate via visit id and subsequent `check.recorded` / `artifact.linked` events.

### Related factory-flow.yaml nodes/checks

| Node | Typical state writes |
|---|---|
| `shape.record` | `approved_ac_version`, plan paths |
| `execute.branch` | `feature_branch`, `default_branch` |
| `execute.plan` | `execution_graph_id` |
| `verify.complete` | `verified_at` |

Enforced by node `allow.state` and implicit `state.nodes.<node_id>.*` per [capabilities.md](../workflow-schema-v1/capabilities.md).

### Cross-links

- [capabilities.md](../workflow-schema-v1/capabilities.md) — allowed state paths
- [cli-artifact.md](cli-artifact.md) — durable outputs via `artifact publish`

---

## transition

### Purpose

Request close on an `opened` visit. Runs `on_close` then `on_seal` hooks; on success the engine seals the visit and selects exactly one eligible connection. **Does not accept a destination node or connection id** — routing is declarative in the registry per [capabilities.md](../workflow-schema-v1/capabilities.md).

Optional accountability fields support builder per-item commits on `execute.build` per [v1-spec.md](../v1-spec.md).

### Who invokes

| Actor | When |
|---|---|
| steward | Step work complete; default allowed CLI on steps |
| engine | Gate close after `gate decide` (internal equivalent) |

Gates with `decider: user` use [cli-gate.md](cli-gate.md) `decide`, not `visit transition`.

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--visit` | no | Visit id (default: active visit) |
| `--summary` | no | Short steward summary (required template fields on `execute.build`) |
| `--receipt` | no | `run:` path to receipt payload file before seal |
| `--commit` | no | Request CLI-performed git commit on `feature_branch` (`execute.build` accountability) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry visit transition --run run-2026-09-24-porcelain-003 --summary "Implemented auth middleware item graph-3." --commit --json
```

### Sample JSON result (success — sealed and routed)

```json
{
  "visit_id": "v-009",
  "node_id": "execute.build",
  "prior_lifecycle": "opened",
  "lifecycle": "sealed",
  "outcome": "completed",
  "connection": {
    "connection_id": "execute.build-to-execute.test",
    "to_node_id": "execute.test"
  },
  "next_visit_id": "v-010",
  "commit_sha": "git:commit/4f91c2a"
}
```

### Sample JSON result (`on_seal` reopen)

When an `on_seal` check selects `reopen` (e.g. `agent-receipt-sealed` failure on `shape.present`):

```json
{
  "visit_id": "v-005",
  "node_id": "shape.present",
  "prior_lifecycle": "closed",
  "lifecycle": "opened",
  "outcome": null,
  "reopened": true,
  "reason": "Presentation receipt missing",
  "policy": {
    "check": "agent-receipt-sealed",
    "action": "reopen"
  }
}
```

No `connection.taken` event; same visit id remains active.

### Hook behavior

| Hook | Trigger | On success | On policy stop |
|---|---|---|---|
| `on_close` | `transition` while `opened` | `lifecycle` → `closed` | Stay `opened`; return check/policy disposition |
| `on_seal` | After `closed` | `lifecycle` → `sealed`, `visit.sealed`, routing | `reopen` → `closed` → `opened`; `halt` / `escalate` → run status change without seal |

Omitted or empty hooks succeed immediately per [visits-lifecycle.md](../workflow-schema-v1/visits-lifecycle.md).

`--receipt` runs [cli-receipt.md](cli-receipt.md) `seal` before the close request, so `receipt.linked` precedes `on_close`. `--commit` performs the accountability commit and records the SHA on the work-item receipt. Commit ownership overlaps [cli-build.md](cli-build.md); see [gaps.md](gaps.md).

### Ledger events appended (successful close and seal)

| Order | Event |
|---|---|
| 1 | `artifact.linked` and `receipt.linked` for publishes and seals that support this close |
| 2+ | `check.recorded`, `policy.applied` per hook check |
| n | `lifecycle.changed` (`opened` → `closed`) |
| n+1 | `lifecycle.changed` (`closed` → `sealed`) |
| n+2 | `visit.sealed` |
| n+3 | Non-terminal: `connection.taken`, then `visit.admitted` on the target. Terminal: `run.status_changed` (`completed`), then `run.completed` |

### Related factory-flow.yaml nodes/checks

| Node | Notable hooks |
|---|---|
| `shape.intake` | `on_seal`: intake + agent receipt checks |
| `shape.present` | `on_seal`: `agent-receipt-sealed` → may `reopen` |
| `shape.record` | `on_seal`: `approved-ac-recorded` |
| `execute.build` | `on_seal`: `validate-build-exit`, `agent-receipt-sealed`; `--commit` accountability |
| `execute.intake` | `on_open`: `validate-git-clean-execute` |
| `execute.commit` | `on_seal`: `final-commit-recorded` |
| `verify.intake` | `on_open`: `validate-verify-context` |

### Cross-links

- [cli-gate.md](cli-gate.md) — user gates use `decide` instead of `transition`
- [cli-receipt.md](cli-receipt.md) — `seal` before the close request when `on_seal` requires `receipt.linked`
- [cli-artifact.md](cli-artifact.md) — publish declared artifacts before close
- [engine.md](../workflow-schema-v1/engine.md) — `close_request` and `seal` procedure
- [control-plane.md](../workflow-schema-v1/control-plane.md) — `reopen`, `halt`, `escalate` actions
