# Node: `verify.intake`

Status: **generated**

Flow: `implementation` in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

Verify intake — branch diff, receipts, and plan alignment

## Lifecycle

Admission is an event (`visit.admitted`), not a lifecycle state. See [visit lifecycle](../concepts/visits-lifecycle.md).

```mermaid
stateDiagram-v2
  direction LR

  [*] --> examined: visit.admitted

  examined --> opened: on_open\nvalidate-manifest\nvalidate-verify-context
  note right of opened
    pass → continue → opened
    fail → halt (default policy)
  end note

  opened --> closed: steward transition\non_close (engine checks)
  note right of closed
    Engine verifies artifact completeness
  end note

  closed --> sealed: on_seal\nintake-receipt-sealed
  note right of sealed
    checks pass → sealed, outcome completed
    fail → reopen (closed → opened)
  end note

  sealed --> [*]: connection.taken\n→ verify.intake.gate
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `prior-execute-commit-sealed`, `feature-branch-set`, `final-commit-recorded` | — |
| `on_open` | `validate-manifest`, `validate-verify-context` | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | `intake-receipt-sealed` | — |

## References

- **Instructions:** [registry:steps/verify-intake.md](../../.cursor/foundry/steps/verify-intake.md)
- **Schemas:**
  - [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json)
  - [registry:schemas/intake-receipt.schema.json](../../.cursor/foundry/schemas/intake-receipt.schema.json)
- **Catalog index:** [verify.intake.index.yaml](../../.cursor/foundry/catalog/nodes/verify.intake.index.yaml)

## Artifacts

### Work artifact: `branch-diff`

| Field | Value |
|---|---|
| **Logical id** | `branch-diff` |
| **Qualified ref** | `verify.intake.branch-diff` |
| **Kind** | `document` |
| **URI** | `run:artifacts/{visit_id}/branch.diff` |
| **Media type** | `text/plain` |

#### Downstream consumption

- [verify.acceptance](verify.acceptance.md) reads `verify.intake.branch-diff` via `nearest_sealed_ancestor`
- [verify.code_quality](verify.code_quality.md) reads `verify.intake.branch-diff` via `nearest_sealed_ancestor`
- [verify.code_review](verify.code_review.md) reads `verify.intake.branch-diff` via `nearest_sealed_ancestor`

## Receipts

| Schema | Role |
|---|---|
| [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json) | Worker completion evidence (`agent-receipt-sealed` on `on_seal`) |
| [registry:schemas/intake-receipt.schema.json](../../.cursor/foundry/schemas/intake-receipt.schema.json) | Intake evidence (`intake-receipt-sealed` on `on_seal`) |

## Worker

| Field | Value |
|---|---|
| **Worker id** | `intake-checker.verify` |
| **Mode** | `verify` |
| **Prompt** | [registry:agents/intake-checker.verify.md](../../.cursor/agents/intake-checker.verify.md) |
| **Contract** | [registry:workers/intake-checker.verify/contract.yaml](../../.cursor/foundry/workers/intake-checker.verify/contract.yaml) |
| **Generated worker doc** | [intake-checker.verify](../catalog/workers/intake-checker.verify.md) |

#### Worker concern ownership

| Concern | Owner |
|---|---|
| `on_examine` / `on_open` / `on_seal` checks | Engine |
| Intake receipt `checks[]` | Steward — from ledger when sealing |
| Work artifact publication | Steward — `artifact.publish` |
| Receipts | Steward — `receipt.link` |
| Worker assessment and proceed/blocked judgment | intake-checker.verify |

## Connections

### Incoming

- `execute.commit.gate-to-verify.intake-pass`: [execute.commit.gate](execute.commit.gate.md) → **verify.intake**

### Outgoing

- `verify.intake-to-verify.intake.gate`: **verify.intake** → [verify.intake.gate](verify.intake.gate.md) (`on.outcomes: ['completed']`)

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
| **id** | `verify.intake` |
| **kind** | `step` |
| **title** | Verify intake — branch diff, receipts, and plan alignment |
