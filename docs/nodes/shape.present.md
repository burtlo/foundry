# Node: `shape.present`

Status: **draft**

Flow: `implementation` in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

Presentation step. Steward launches shape-presenter to propose succinct plan markdown, writes presentation once, publishes the artifact, seals agent receipt, and transitions to the presentation gate.


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

## Sequence

```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant S as Steward (shape parent)
  participant CLI as foundry CLI
  participant E as Engine
  participant W as Worker (shape-presenter)

  S->>CLI: run context --markdown
  CLI-->>S: steward packet (draft_ac, ticket + inlined instructions)

  S->>W: launch shape-presenter
  W-->>S: presentation draft, presented_ac, PROCEED/BLOCKED verdict

  S->>CLI: ledger show
  S->>CLI: visit state patch (presented_ac)
  S->>CLI: artifact publish (presentation)
  S->>CLI: receipt seal (agent)
  S->>CLI: visit transition
  CLI->>E: close, on_seal checks, route to shape.present.gate
  CLI-->>S: sealed, next visit shape.present.gate
```

## References

- **Instructions:** [registry:nodes/shape.present/instructions.md](../../.cursor/foundry/nodes/shape.present/instructions.md)
- **Schemas:**
  - [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json)
- **Catalog index:** [shape.present.index.yaml](../../.cursor/foundry/catalog/nodes/shape.present.index.yaml)

## Ownership

| Role | Owner |
|---|---|
| **worker** | shape-presenter |
| **steward** | shape parent agent |
| **engine** | on_examine prior-examine-sealed, artifact completeness on close, on_seal agent-receipt check |

## Permissions

### `reads`

| Namespace | Paths |
|---|---|
| `state` | `draft_ac`, `assumptions`, `ticket`, `examination_decisions`, `clarifying_questions`, `questions_asked_total`, `examination_round` |

### `allow`

| Namespace | Grant | Purpose |
|---|---|---|
| `state` | `presented_ac`, `presentation_artifact_path`, `state.nodes.shape.present.*` | Domain fields |
| `files.write` | `run:artifacts/{visit_id}/presentation.md`, `run:receipts/{visit_id}/assessment.md`, `run:receipts/agent.json` | Writable run paths |
| `cli` | `artifact.publish`, `ledger.show`, `receipt.link`, `transition`, `visit.state_patch` | Steward CLI capabilities |
| `worker` | bound worker | Authorized without `allow.agents` |

### Steward CLI capabilities

| Capability |
|---|
| `artifact.publish` |
| `ledger.show` |
| `receipt.link` |
| `transition` |
| `visit.state_patch` |

### Engine-only surfaces

| Surface | Trigger | Maps to |
|---|---|---|
| `foundry run create` | New run bootstrap | Admit entry visit, run `on_open` |
| `prior-examine-sealed` | `on_examine` hook | `on_examine` check `prior-examine-sealed` |
| `agent-receipt-sealed` | `on_seal` hook | `on_seal` check `agent-receipt-sealed` |
| Artifact completeness | `close_request` before `closed` | Every `produces.artifacts` declaration satisfied |
| Connection selection | After `visit.sealed` | Routes to `shape.present.gate` |

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

- [shape.present.gate](shape.present.gate.md) reads `shape.present.presentation` via `nearest_sealed_ancestor`
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
| `on_examine` / `on_open` / `on_seal` checks | on_examine prior-examine-sealed, artifact completeness on close, on_seal agent-receipt check |
| Intake receipt `checks[]` | shape parent agent — from ledger when sealing |
| Work artifact publication | shape parent agent — `artifact.publish` |
| Receipts | shape parent agent — `receipt.link` |
| Worker assessment and proceed/blocked judgment | shape-presenter |

## Connections

### Incoming

- `shape.examine-to-shape.present`: [shape.examine](shape.examine.md) → **shape.present**
- `shape.examine.gate-to-shape.present-present`: [shape.examine.gate](shape.examine.gate.md) → **shape.present**

### Outgoing

- `shape.present-to-shape.present.gate`: **shape.present** → [shape.present.gate](shape.present.gate.md) (`on.outcomes: ['completed']`)

## Check catalog

### `prior-examine-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.last('visit.sealed', node_id='shape.examine') != null && history.last('visit.sealed', node_id='shape.examine').outcome == 'completed'` |
| **Hook** | `on_examine` |

### `agent-receipt-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.count('receipt.linked', visit_id=visit.id, schema='registry:schemas/agent-receipt.schema.json') >= 1` |
| **Hook** | `on_seal` |
| **on_fail** | `reopen` — Presentation receipt missing |

## Gaps

- reads.artifacts nearest_sealed_ancestor for ticket is declared in registry but ticket is read from state today

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
