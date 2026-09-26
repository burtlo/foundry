# Node: `shape.record`

Status: **generated**

Flow: `implementation` in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

Shape record — freeze approved_ac and living plan

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

## References

- **Instructions:** [registry:steps/shape-record.md](../../.cursor/foundry/steps/shape-record.md)
- **Schemas:**
  - [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json)
- **Catalog index:** [shape.record.index.yaml](../../.cursor/foundry/catalog/nodes/shape.record.index.yaml)

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
- [verify.acceptance](verify.acceptance.md) reads `shape.record.plan` via `nearest_sealed_ancestor`
- [verify.intake](verify.intake.md) reads `shape.record.plan` via `nearest_sealed_ancestor`

## Receipts

| Schema | Role |
|---|---|
| [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json) | Worker completion evidence (`agent-receipt-sealed` on `on_seal`) |

## Worker

| Field | Value |
|---|---|
| **Worker id** | `shape-recorder` |
| **Mode** | `shape` |
| **Prompt** | [registry:agents/shape-recorder.md](../../.cursor/agents/shape-recorder.md) |
| **Contract** | [registry:workers/shape-recorder/contract.yaml](../../.cursor/foundry/workers/shape-recorder/contract.yaml) |
| **Generated worker doc** | [shape-recorder](../catalog/workers/shape-recorder.md) |

#### Worker concern ownership

| Concern | Owner |
|---|---|
| `on_examine` / `on_open` / `on_seal` checks | Engine |
| Intake receipt `checks[]` | Steward — from ledger when sealing |
| Work artifact publication | Steward — `artifact.publish` |
| Receipts | Steward — `receipt.link` |
| Worker assessment and proceed/blocked judgment | shape-recorder |

## Connections

### Incoming

- `shape.present.gate-to-shape.record-record`: [shape.present.gate](shape.present.gate.md) → **shape.record**

### Outgoing

- `shape.record-to-shape.record.gate`: **shape.record** → [shape.record.gate](shape.record.gate.md) (`on.outcomes: ['completed']`)

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
