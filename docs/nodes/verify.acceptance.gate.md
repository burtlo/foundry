# Node: `verify.acceptance.gate`

Status: **ok**

Flow: `implementation` in [flows/implementation/registry.yaml](../../.cursor/foundry/flows/implementation/registry.yaml).

Engine gate after verify.acceptance when findings and agent receipt are sealed. The host or steward uses run advance to resolve pass, replan, reshape, or rework_execute from verify-findings gate_decision. No user gate decide and no worker.

## Contents

- [Lifecycle](#lifecycle)
- [Sequence](#sequence)
- [Ledger excerpt](#ledger-excerpt)
- [References](#references)
- [Permissions](#permissions)
- [Artifacts](#artifacts)
- [Receipts](#receipts)
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

  sealed --> [*]: connection.taken\n→ verify.code_quality, execute.plan, shape.intake, execute.intake
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `prior-verify-acceptance-sealed` | — |
| `on_open` | *(empty)* | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | *(empty)* | — |

## Sequence

_Sequence diagram not authored in `doc.yaml`._

## References

- **Gate prompt:** `Route the verified acceptance result to quality review, replanning, reshaping, or execution rework.`
- **Catalog index:** [verify.acceptance.gate.index.yaml](../catalog/implementation/nodes/verify.acceptance.gate.index.yaml)

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
| `prior-verify-acceptance-sealed` | `on_examine` hook | `on_examine` check `prior-verify-acceptance-sealed` |
| Artifact completeness | `close_request` before `closed` | Every `produces.artifacts` declaration satisfied |
| Connection selection | After `visit.sealed` | Routes to `verify.code_quality`, `execute.plan`, `shape.intake`, `execute.intake` |

## Artifacts

_No work artifacts declared._

## Receipts

_No receipts declared._

## Connections

### Incoming

- `verify.acceptance-to-verify.acceptance.gate`: [verify.acceptance](verify.acceptance.md) → **verify.acceptance.gate**

### Outgoing

- `verify.acceptance.gate-to-verify.code_quality-pass`: **verify.acceptance.gate** → [verify.code_quality](verify.code_quality.md) (`on.outcomes: ['completed']`)
- `verify.acceptance.gate-to-execute.plan-replan`: **verify.acceptance.gate** → [execute.plan](execute.plan.md) (`on.outcomes: ['completed']`)
- `verify.acceptance.gate-to-shape.intake-reshape`: **verify.acceptance.gate** → [shape.intake](shape.intake.md) (`on.outcomes: ['completed']`)
- `verify.acceptance.gate-to-execute.intake-rework_execute`: **verify.acceptance.gate** → [execute.intake](execute.intake.md) (`on.outcomes: ['completed']`)

## Check catalog

### `prior-verify-acceptance-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.last('visit.sealed', node_id='verify.acceptance') != null && history.last('visit.sealed', node_id='verify.acceptance').outcome == 'completed'` |
| **Hook** | `on_examine` |

## Concepts

- **Lifecycle:** [Visit lifecycle](../concepts/visits-lifecycle.md)
- **Connections:** [Graph and routing](../concepts/graph.md)
- **Checks:** [Control plane](../concepts/control-plane.md)
- **Gate decisions:** [Gate nodes](../concepts/graph.md)

## Node summary

| Field | Value |
|---|---|
| **id** | `verify.acceptance.gate` |
| **kind** | `gate` |
| **title** | Acceptance result routing |
