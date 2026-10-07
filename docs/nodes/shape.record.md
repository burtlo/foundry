# Node: `shape.record`

Status: **implemented**

Flow: `implementation` in [flows/implementation/registry.yaml](../../.cursor/foundry/flows/implementation/registry.yaml).

Record step. Steward runs the shape.record task, submits structured judgment, and calls visit record complete. Engine publishes plan, patches approved_ac state, mirrors workspace plan, seals agent receipt, and routes to the record gate.

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

  closed --> sealed: on_seal\napproved-ac-recorded\nagent-receipt-sealed
  note right of sealed
    checks pass → sealed, outcome completed
    fail → reopen (closed → opened)
  end note

  sealed --> [*]: connection.taken\n→ shape.record.gate
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `prior-present-sealed` | — |
| `on_open` | *(empty)* | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | `approved-ac-recorded`, `agent-receipt-sealed` | — |

## Sequence

_Sequence diagram not authored in `doc.yaml`._

## References

- **Instructions:** [registry:nodes/shape.record/judgment.md](../../.cursor/foundry/nodes/shape.record/judgment.md)
- **Schemas:**
  - [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json)
- **Catalog index:** [shape.record.index.yaml](../catalog/implementation/nodes/shape.record.index.yaml)

## Permissions

### `reads`

| Namespace | Paths |
|---|---|
| `state` | `presented_ac`, `presentation_artifact_path`, `approved_ac` |
| `artifacts` | `shape.present.presentation` |

### `allow`

| Namespace | Grant | Purpose |
|---|---|---|
| `cli` | `run.agent.submit`, `visit.record.complete` | Steward CLI capabilities |

### Steward CLI capabilities

| Capability |
|---|
| `run.agent.submit` |
| `visit.record.complete` |

### Engine-only surfaces

| Surface | Trigger | Maps to |
|---|---|---|
| `foundry run create` | New run bootstrap | Admit entry visit, run `on_open` |
| `prior-present-sealed` | `on_examine` hook | `on_examine` check `prior-present-sealed` |
| `approved-ac-recorded` | `on_seal` hook | `on_seal` check `approved-ac-recorded` |
| `agent-receipt-sealed` | `on_seal` hook | `on_seal` check `agent-receipt-sealed` |
| Artifact completeness | `close_request` before `closed` | Every `produces.artifacts` declaration satisfied |
| Connection selection | After `visit.sealed` | Routes to `shape.record.gate` |

## Artifacts

### Work artifact: `plan`

| Field | Value |
|---|---|
| **Logical id** | `plan` |
| **Qualified ref** | `shape.record.plan` |
| **Kind** | `document` |
| **URI** | `run:artifacts/{visit_id}/plan.md` |
| **Media type** | `text/markdown` |

#### Downstream consumption

- [execute.intake](execute.intake.md) reads `shape.record.plan` via `nearest_sealed_ancestor`
- [execute.plan](execute.plan.md) reads `shape.record.plan` via `nearest_sealed_ancestor`
- [execute.start](execute.start.md) reads `shape.record.plan` via `nearest_sealed_ancestor`
- [shape.record.gate](shape.record.gate.md) reads `shape.record.plan` via `nearest_sealed_ancestor`
- [verify.acceptance](verify.acceptance.md) reads `shape.record.plan` via `nearest_sealed_ancestor`
- [verify.intake](verify.intake.md) reads `shape.record.plan` via `nearest_sealed_ancestor`

## Receipts

| Schema | Role |
|---|---|
| [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json) | Worker completion evidence (`agent-receipt-sealed` on `on_seal`) |

## Worker

_No worker bound._

## Connections

### Incoming

- `shape.present.gate-to-shape.record-record`: [shape.present.gate](shape.present.gate.md) → **shape.record**

### Outgoing

- `shape.record-to-shape.record.gate`: **shape.record** → [shape.record.gate](shape.record.gate.md) (`on.outcomes: ['completed']`)

## Check catalog

### `prior-present-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.last('visit.sealed', node_id='shape.present') != null && history.last('visit.sealed', node_id='shape.present').outcome == 'completed'` |
| **Hook** | `on_examine` |

### `approved-ac-recorded`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `state.approved_ac_version >= 1` |
| **Hook** | `on_seal` |
| **on_fail** | `reopen` — approved_ac not recorded |

### `agent-receipt-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.count('receipt.linked', visit_id=visit.id, schema='registry:schemas/agent-receipt.schema.json') >= 1` |
| **Hook** | `on_seal` |
| **on_fail** | `reopen` — Shape record receipt not sealed |

## Concepts

- **Lifecycle:** [Visit lifecycle](../concepts/visits-lifecycle.md)
- **Connections:** [Graph and routing](../concepts/graph.md)
- **Permissions:** [Reads and allow](../concepts/capabilities.md)
- **Artifacts:** [Artifact publication](../concepts/artifacts.md)
- **Receipts:** [Receipts vs artifacts](../concepts/artifacts.md)
- **Checks:** [Control plane](../concepts/control-plane.md)

## Node summary

| Field | Value |
|---|---|
| **id** | `shape.record` |
| **kind** | `step` |
| **title** | Shape record — freeze approved_ac and living plan |
