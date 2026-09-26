# Node: `verify.code_quality`

Status: **generated**

Flow: `implementation` in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

Automated lint, Bugbot, and security review

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

  sealed --> [*]: connection.taken\n→ verify.code_quality.gate, verify.code_review
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `prior-verify-acceptance-sealed`, `review-enabled` | — |
| `on_open` | *(empty)* | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | `agent-receipt-sealed` | — |

## References

- **Instructions:** [registry:steps/verify-code-quality.md](../../.cursor/foundry/steps/verify-code-quality.md)
- **Schemas:**
  - [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json)
- **Catalog index:** [verify.code_quality.index.yaml](../../.cursor/foundry/catalog/nodes/verify.code_quality.index.yaml)

## Artifacts

### Work artifact: `code-quality-report`

| Field | Value |
|---|---|
| **Logical id** | `code-quality-report` |
| **Qualified ref** | `verify.code_quality.code-quality-report` |
| **Kind** | `document` |
| **URI** | `run:artifacts/{visit_id}/code-quality-report.md` |
| **Media type** | `text/markdown` |


## Receipts

| Schema | Role |
|---|---|
| [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json) | Worker completion evidence (`agent-receipt-sealed` on `on_seal`) |

## Worker

_No worker bound._

## Connections

### Incoming

- `verify.acceptance.gate-to-verify.code_quality-pass`: [verify.acceptance.gate](verify.acceptance.gate.md) → **verify.code_quality**

### Outgoing

- `verify.code_quality-to-verify.code_quality.gate`: **verify.code_quality** → [verify.code_quality.gate](verify.code_quality.gate.md) (`on.outcomes: ['completed']`)
- `verify.code_quality-to-verify.code_review-skipped`: **verify.code_quality** → [verify.code_review](verify.code_review.md) (`on.outcomes: ['not_applicable']`)

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
| **id** | `verify.code_quality` |
| **kind** | `step` |
| **title** | Automated lint, Bugbot, and security review |
