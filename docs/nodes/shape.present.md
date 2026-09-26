# Node: `shape.present`

Status: **generated**

Flow: `implementation` in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

Shape present — succinct plan and AC presentation

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

  closed --> sealed: on_seal\nagent-receipt-sealed
  note right of sealed
    checks pass → sealed, outcome completed
    fail → reopen (closed → opened)
  end note

  sealed --> [*]: connection.taken\n→ shape.present.gate
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `prior-examine-sealed` | — |
| `on_open` | *(empty)* | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | `agent-receipt-sealed` | — |

## References

- **Instructions:** [registry:steps/shape-present.md](../../.cursor/foundry/steps/shape-present.md)
- **Schemas:**
  - [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json)
- **Catalog index:** [shape.present.index.yaml](../../.cursor/foundry/catalog/nodes/shape.present.index.yaml)

## Artifacts

### Work artifact: `presentation`

| Field | Value |
|---|---|
| **Logical id** | `presentation` |
| **Qualified ref** | `shape.present.presentation` |
| **Kind** | `document` |
| **URI** | `run:artifacts/{visit_id}/presentation.md` |
| **Media type** | `text/markdown` |

#### Downstream consumption

- [shape.record](shape.record.md) reads `shape.present.presentation` via `nearest_sealed_ancestor`

## Receipts

| Schema | Role |
|---|---|
| [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json) | Worker completion evidence (`agent-receipt-sealed` on `on_seal`) |

## Worker

| Field | Value |
|---|---|
| **Worker id** | `shape-presenter` |
| **Mode** | `shape` |
| **Prompt** | [registry:agents/shape-presenter.md](../../.cursor/agents/shape-presenter.md) |
| **Contract** | [registry:workers/shape-presenter/contract.yaml](../../.cursor/foundry/workers/shape-presenter/contract.yaml) |
| **Generated worker doc** | [shape-presenter](../catalog/workers/shape-presenter.md) |

#### Worker concern ownership

| Concern | Owner |
|---|---|
| `on_examine` / `on_open` / `on_seal` checks | Engine |
| Intake receipt `checks[]` | Steward — from ledger when sealing |
| Work artifact publication | Steward — `artifact.publish` |
| Receipts | Steward — `receipt.link` |
| Worker assessment and proceed/blocked judgment | shape-presenter |

## Connections

### Incoming

- `shape.examine-to-shape.present`: [shape.examine](shape.examine.md) → **shape.present**
- `shape.examine.gate-to-shape.present-present`: [shape.examine.gate](shape.examine.gate.md) → **shape.present**

### Outgoing

- `shape.present-to-shape.present.gate`: **shape.present** → [shape.present.gate](shape.present.gate.md) (`on.outcomes: ['completed']`)

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
| **id** | `shape.present` |
| **kind** | `step` |
| **title** | Shape present — succinct plan and AC presentation |
