# Node: `execute.repair.limit.gate`

Status: **ok**

Flow: `implementation` in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

Engine gate where all repair routes converge. Counts prior repair-loop connection.taken events against config.limits.repair; on_examine repair-within-limit escalates when over limit. The host or steward uses run advance to resolve proceed and re-enter execute.build. No user gate decide and no worker.


## Contents

- [Lifecycle](#lifecycle)
- [Sequence](#sequence)
- [Ledger excerpt](#ledger-excerpt)
- [References](#references)
- [Permissions](#permissions)
- [Artifacts](#artifacts)
- [Receipts](#receipts)
- [Worker](#worker)
- [Connections](#connections)
- [Check catalog](#check-catalog)
- [Gaps](#gaps)

---

## Lifecycle

Admission is an event (`visit.admitted`), not a lifecycle state. See [visit lifecycle](../concepts/visits-lifecycle.md).

```mermaid
stateDiagram-v2
  direction LR

  [*] --> examined: visit.admitted

  examined --> opened: on_open\n(none)
  note right of opened
    pass → continue → opened
    fail → halt (default policy)
  end note

  opened --> closed: steward transition\non_close (engine checks)
  note right of closed
    Engine verifies artifact completeness
  end note

  closed --> sealed: on_seal\n(none)
  note right of sealed
    checks pass → sealed, outcome completed
    fail → reopen (closed → opened)
  end note

  sealed --> [*]: connection.taken\n→ execute.build
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `repair-within-limit` | — |
| `on_open` | *(empty)* | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | *(empty)* | — |

## Sequence

```mermaid
sequenceDiagram
  autonumber
  participant S as Steward / host
  participant CLI as foundry CLI
  participant E as Engine

  Note over E: repair route (test/verify) admits repair limit gate
  E->>E: on_examine repair-within-limit
  S->>CLI: run advance --json
  CLI->>E: resolve_engine_gate (count vs config.limits.repair)
  CLI->>E: seal gate, route proceed to execute.build (repair loop)
  CLI-->>S: active visit execute.build
```

## References

- **Gate prompt:** `Machine gate. All repair routes converge here. Count prior repair loops; escalate when config.limits.repair is exceeded so the operator can resume when ready.`
- **Catalog index:** [execute.repair.limit.gate.index.yaml](../../.cursor/foundry/catalog/nodes/execute.repair.limit.gate.index.yaml)

## Ownership

| Role | Owner |
|---|---|
| **worker** | none |
| **steward** | execute parent / craft steward |
| **engine** | on_examine repair-within-limit (escalate on_fail), resolve_engine_gate proceed, route to execute.build |

## Permissions

### `reads`

| Namespace | Paths |
|---|---|
| — | *(none declared)* |

### `allow`

| Namespace | Grant | Purpose |
|---|---|---|
| — | *(none declared)* | — |

### Engine-only surfaces

| Surface | Trigger | Maps to |
|---|---|---|
| `foundry run create` | New run bootstrap | Admit entry visit, run `on_open` |
| `repair-within-limit` | `on_examine` hook | `on_examine` check `repair-within-limit` |
| Artifact completeness | `close_request` before `closed` | Every `produces.artifacts` declaration satisfied |
| Connection selection | After `visit.sealed` | Routes to `execute.build` |

## Artifacts

_No work artifacts declared._

## Receipts

_No receipts declared._

## Connections

### Incoming

- `execute.test.gate-to-execute.repair.limit.gate-repair`: [execute.test.gate](execute.test.gate.md) → **execute.repair.limit.gate**
- `verify.code_quality.gate-to-execute.repair.limit.gate-repair`: [verify.code_quality.gate](verify.code_quality.gate.md) → **execute.repair.limit.gate**
- `verify.code_review.gate-to-execute.repair.limit.gate-repair`: [verify.code_review.gate](verify.code_review.gate.md) → **execute.repair.limit.gate**

### Outgoing

- `execute.repair.limit.gate-to-execute.build-proceed`: **execute.repair.limit.gate** → [execute.build](execute.build.md) (`on.outcomes: ['completed']`)

## Check catalog

### `repair-within-limit`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.count('connection.taken', loop='repair') <= config.limits.repair` |
| **Hook** | `on_examine` |
| **on_fail** | `escalate` — Repair loop limit reached |

## Concepts

- **Lifecycle:** [Visit lifecycle](../concepts/visits-lifecycle.md)
- **Connections:** [Graph and routing](../concepts/graph.md)
- **Checks:** [Control plane](../concepts/control-plane.md)
- **Gate decisions:** [Gate nodes](../concepts/graph.md)

## Node summary

| Field | Value |
|---|---|
| **id** | `execute.repair.limit.gate` |
| **kind** | `gate` |
| **title** | Repair loop guard — count prior repair cycles before build |
