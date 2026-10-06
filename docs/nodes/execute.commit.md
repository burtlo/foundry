# Node: `execute.commit`

Status: **generated**

Flow: `implementation` in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

Final summarizing commit on feature branch

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

  closed --> sealed: on_seal\nfinal-commit-recorded\nagent-receipt-sealed
  note right of sealed
    checks pass → sealed, outcome completed
    fail → reopen (closed → opened)
  end note

  sealed --> [*]: connection.taken\n→ execute.commit.gate
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `prior-execute-test-sealed` | — |
| `on_open` | *(empty)* | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | `final-commit-recorded`, `agent-receipt-sealed` | — |

## References

- **Instructions:** [registry:steps/execute-commit.md](../../.cursor/foundry/steps/execute-commit.md)
- **Schemas:**
  - [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json)
- **Catalog index:** [execute.commit.index.yaml](../../.cursor/foundry/catalog/nodes/execute.commit.index.yaml)

## Artifacts

### Work artifact: `final-commit`

| Field | Value |
|---|---|
| **Logical id** | `final-commit` |
| **Qualified ref** | `execute.commit.final-commit` |
| **Kind** | `reference` |

#### Downstream consumption

- [verify.intake](verify.intake.md) reads `execute.commit.final-commit` via `nearest_sealed_ancestor`

## Receipts

| Schema | Role |
|---|---|
| [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json) | Worker completion evidence (`agent-receipt-sealed` on `on_seal`) |

## Worker

| Field | Value |
|---|---|
| **Worker id** | `commit-agent` |
| **Mode** | `execute` |
| **Prompt** | [registry:agents/commit-agent.md](../../.cursor/agents/commit-agent.md) |
| **Contract** | [registry:workers/commit-agent/contract.yaml](../../.cursor/foundry/workers/commit-agent/contract.yaml) |
| **Generated worker doc** | [commit-agent](../catalog/workers/commit-agent.md) |

#### Worker concern ownership

| Concern | Owner |
|---|---|
| `on_examine` / `on_open` / `on_seal` checks | Engine |
| Intake receipt `checks[]` | Steward — from ledger when sealing |
| Work artifact publication | Steward — `artifact.publish` |
| Receipts | Steward — `receipt.link` |
| Worker assessment and proceed/blocked judgment | commit-agent |

## Connections

### Incoming

- `execute.test.gate-to-execute.commit-pass`: [execute.test.gate](execute.test.gate.md) → **execute.commit**

### Outgoing

- `execute.commit-to-execute.commit.gate`: **execute.commit** → [execute.commit.gate](execute.commit.gate.md) (`on.outcomes: ['completed']`)

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
| **id** | `execute.commit` |
| **kind** | `step` |
| **title** | Final summarizing commit on feature branch |
