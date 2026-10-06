# Node: `verify.intake.gate`

Status: **ok**

Flow: `implementation` in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

Engine gate after verify.intake when intake receipts are sealed. The host or steward uses run advance to resolve pass from the intake receipt status and route to verify.acceptance. No user gate decide and no worker.


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

  sealed --> [*]: connection.taken\n→ verify.acceptance
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `prior-verify-intake-sealed`, `intake-receipt-sealed` | — |
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

  Note over E: verify.intake sealed with passed intake receipt
  E->>E: admit verify.intake.gate, on_examine checks
  S->>CLI: run advance --json
  CLI->>E: resolve_engine_gate (intake receipt status passed)
  CLI->>E: seal gate, route to verify.acceptance
  CLI-->>S: active visit verify.acceptance
```

## References

- **Gate prompt:** `Machine gate. Intake receipt must exit 0 — CLI checks plus agent assessment when configured.`
- **Catalog index:** [verify.intake.gate.index.yaml](../../.cursor/foundry/catalog/nodes/verify.intake.gate.index.yaml)

## Ownership

| Role | Owner |
|---|---|
| **worker** | none |
| **steward** | verify parent / craft steward |
| **engine** | on_examine prior-verify-intake-sealed and intake-receipt-sealed, resolve_engine_gate, route on pass |

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
| `prior-verify-intake-sealed` | `on_examine` hook | `on_examine` check `prior-verify-intake-sealed` |
| `intake-receipt-sealed` | `on_examine` hook | `on_examine` check `intake-receipt-sealed` |
| Artifact completeness | `close_request` before `closed` | Every `produces.artifacts` declaration satisfied |
| Connection selection | After `visit.sealed` | Routes to `verify.acceptance` |

## Artifacts

_No work artifacts declared._

## Receipts

_No receipts declared._

## Connections

### Incoming

- `verify.intake-to-verify.intake.gate`: [verify.intake](verify.intake.md) → **verify.intake.gate**

### Outgoing

- `verify.intake.gate-to-verify.acceptance-pass`: **verify.intake.gate** → [verify.acceptance](verify.acceptance.md) (`on.outcomes: ['completed']`)

## Check catalog

### `prior-verify-intake-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.last('visit.sealed', node_id='verify.intake') != null && history.last('visit.sealed', node_id='verify.intake').outcome == 'completed'` |
| **Hook** | `on_examine` |

### `intake-receipt-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.count('receipt.linked', visit_id=visit.id, schema='registry:schemas/intake-receipt.schema.json') >= 1` |
| **Hook** | `on_examine` |
| **on_fail** | `halt` — Verify intake blocked |

## Concepts

- **Lifecycle:** [Visit lifecycle](../concepts/visits-lifecycle.md)
- **Connections:** [Graph and routing](../concepts/graph.md)
- **Checks:** [Control plane](../concepts/control-plane.md)
- **Gate decisions:** [Gate nodes](../concepts/graph.md)

## Node summary

| Field | Value |
|---|---|
| **id** | `verify.intake.gate` |
| **kind** | `gate` |
| **title** | Verify intake blocked check |
