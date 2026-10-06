# Node: `verify.complete.gate`

Status: **generated**

Flow: `implementation` in [factory-flow.yaml](../../../../../flows/factory-flow.yaml).

Verify complete

## Lifecycle

Admission is an event (`visit.admitted`), not a lifecycle state. See [visit lifecycle](../../../../../cli/docs/concepts/visits-lifecycle.md).

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

  sealed --> [*]: connection.taken\n→ deliver.stub
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | *(empty)* | — |
| `on_open` | *(empty)* | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | *(empty)* | — |

## References

- **Instructions:** [registry:nodes/verify.complete.gate/instructions.md](../../../../../nodes/verify.complete.gate/instructions.md)
- **Gate prompt:** `User accepts the implementation. Accept to end the verify phase and proceed to deliver.`
- **Catalog index:** [verify.complete.gate.index.yaml](../../../../../catalog/nodes/verify.complete.gate.index.yaml)

## Artifacts

_No work artifacts declared._

## Receipts

_No receipts declared._

## Connections

### Incoming

- `verify.complete-to-verify.complete.gate`: [verify.complete](verify.complete.md) → **verify.complete.gate**

### Outgoing

- `verify.complete.gate-to-deliver.stub-complete`: **verify.complete.gate** → [deliver.stub](deliver.stub.md) (`on.outcomes: ['completed']`)

## Concepts

- **Lifecycle:** [Visit lifecycle](../../../../../cli/docs/concepts/visits-lifecycle.md)
- **Connections:** [Graph and routing](../../../../../cli/docs/concepts/graph.md)
- **Permissions:** [Reads and allow](../../../../../cli/docs/concepts/capabilities.md)
- **Gate decisions:** [Gate nodes](../../../../../cli/docs/concepts/graph.md)

## Node summary

| Field | Value |
|---|---|
| **id** | `verify.complete.gate` |
| **kind** | `gate` |
| **title** | Verify complete |
