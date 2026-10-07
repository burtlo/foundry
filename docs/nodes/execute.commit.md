# Node: `execute.commit`

Status: **ok**

Flow: `implementation` in [flows/implementation/registry.yaml](../../.cursor/foundry/flows/implementation/registry.yaml).

Host-owned final commit step after execute.test.gate pass. Checks out the feature branch, records a git commit (empty allowed in stub mode), publishes final-commit, patches final_commit_sha and execute_commit_message, seals a commit-agent receipt, and routes to execute.commit.gate.

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

## Sequence

_Sequence diagram not authored in `doc.yaml`._

## References

- **Schemas:**
  - [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json)
- **Catalog index:** [execute.commit.index.yaml](../catalog/implementation/nodes/execute.commit.index.yaml)

## Permissions

### `reads`

| Namespace | Paths |
|---|---|
| `config` | `git` |
| `state` | `execution_graph_id`, `feature_branch` |
| `artifacts` | `execute.plan.execution-graph` |

### `allow`

| Namespace | Grant | Purpose |
|---|---|---|
| `state` | `final_commit_sha`, `execute_commit_message`, `state.nodes.execute.commit.*` | Domain fields |

### Engine-only surfaces

| Surface | Trigger | Maps to |
|---|---|---|
| `foundry run create` | New run bootstrap | Admit entry visit, run `on_open` |
| `prior-execute-test-sealed` | `on_examine` hook | `on_examine` check `prior-execute-test-sealed` |
| `final-commit-recorded` | `on_seal` hook | `on_seal` check `final-commit-recorded` |
| `agent-receipt-sealed` | `on_seal` hook | `on_seal` check `agent-receipt-sealed` |
| Artifact completeness | `close_request` before `closed` | Every `produces.artifacts` declaration satisfied |
| Connection selection | After `visit.sealed` | Routes to `execute.commit.gate` |

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

## Connections

### Incoming

- `execute.test.gate-to-execute.commit-pass`: [execute.test.gate](execute.test.gate.md) → **execute.commit**

### Outgoing

- `execute.commit-to-execute.commit.gate`: **execute.commit** → [execute.commit.gate](execute.commit.gate.md) (`on.outcomes: ['completed']`)

## Check catalog

### `prior-execute-test-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.last('visit.sealed', node_id='execute.test') != null && history.last('visit.sealed', node_id='execute.test').outcome == 'completed'` |
| **Hook** | `on_examine` |

### `final-commit-recorded`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `state.final_commit_sha != null` |
| **Hook** | `on_seal` |
| **on_fail** | `reopen` — Final commit not recorded |

### `agent-receipt-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.count('receipt.linked', visit_id=visit.id, schema='registry:schemas/agent-receipt.schema.json') >= 1` |
| **Hook** | `on_seal` |

## Gaps

- optional execute_commit_message state override is not exposed in steward UI

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
