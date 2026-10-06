# Node: `verify.acceptance`

Status: **ok**

Flow: `implementation` in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

Host-owned deterministic acceptance assessment after verify intake gate pass. Publishes verify-findings with gate_decision from sealed execute context (AC, tests, diff usability); seals implementation-validator-labeled agent receipt; routes to verify.acceptance.gate.


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

  sealed --> [*]: connection.taken\n→ verify.acceptance.gate
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `prior-verify-intake-sealed` | — |
| `on_open` | *(empty)* | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | `agent-receipt-sealed` | — |

## Sequence

```mermaid
sequenceDiagram
  autonumber
  participant S as Steward
  participant CLI as foundry CLI
  participant E as Engine

  Note over S,E: After verify.intake.gate pass
  CLI->>E: admit verify.acceptance, on_examine prior-verify-intake-sealed
  CLI->>E: run advance (opened) → run_verify_acceptance_complete
  E->>E: _assess_acceptance → gate_decision + evidence_ok
  E->>E: publish verify-findings, seal agent receipt, transition
  CLI-->>S: sealed → verify.acceptance.gate

  Note over S,E: implementation-validator worker is legacy and unbound; happy path does not invoke it.
```

## References

- **Schemas:**
  - [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json)
- **Catalog index:** [verify.acceptance.index.yaml](../../.cursor/foundry/catalog/nodes/verify.acceptance.index.yaml)

## Ownership

| Role | Owner |
|---|---|
| **worker** | legacy implementation-validator (unbound — not on happy path) |
| **steward** | verify parent / craft steward — use run advance only; do not bind worker for findings |
| **engine** | on_examine prior-verify-intake-sealed; run_verify_acceptance_complete via run advance |

## Permissions

### `reads`

| Namespace | Paths |
|---|---|
| `state` | `approved_ac`, `execution_graph_id`, `branch_diff_artifact_path`, `final_commit_sha`, `last_test_exit_code` |
| `artifacts` | `shape.record.plan`, `verify.intake.branch-diff` |

### `allow`

| Namespace | Grant | Purpose |
|---|---|---|
| `state` | `verify_findings`, `state.nodes.verify.acceptance.*` | Domain fields |

### Engine-only surfaces

| Surface | Trigger | Maps to |
|---|---|---|
| `foundry run create` | New run bootstrap | Admit entry visit, run `on_open` |
| `prior-verify-intake-sealed` | `on_examine` hook | `on_examine` check `prior-verify-intake-sealed` |
| `agent-receipt-sealed` | `on_seal` hook | `on_seal` check `agent-receipt-sealed` |
| Artifact completeness | `close_request` before `closed` | Every `produces.artifacts` declaration satisfied |
| Connection selection | After `visit.sealed` | Routes to `verify.acceptance.gate` |

## Artifacts

### Work artifact: `verify-findings`

| Field | Value |
|---|---|
| **Logical id** | `verify-findings` |
| **Qualified ref** | `verify.acceptance.verify-findings` |
| **Kind** | `document` |
| **URI** | `run:artifacts/{visit_id}/verify-findings.json` |
| **Media type** | `application/json` |

#### Downstream consumption

- [verify.code_review](verify.code_review.md) reads `verify.acceptance.verify-findings` via `nearest_sealed_ancestor`
- [verify.code_review.gate](verify.code_review.gate.md) reads `verify.acceptance.verify-findings` via `nearest_sealed_ancestor`

## Receipts

| Schema | Role |
|---|---|
| [registry:schemas/agent-receipt.schema.json](../../.cursor/foundry/schemas/agent-receipt.schema.json) | Worker completion evidence (`agent-receipt-sealed` on `on_seal`) |

## Worker

_No worker bound._

## Connections

### Incoming

- `verify.intake.gate-to-verify.acceptance-pass`: [verify.intake.gate](verify.intake.gate.md) → **verify.acceptance**

### Outgoing

- `verify.acceptance-to-verify.acceptance.gate`: **verify.acceptance** → [verify.acceptance.gate](verify.acceptance.gate.md) (`on.outcomes: ['completed']`)

## Check catalog

### `prior-verify-intake-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.last('visit.sealed', node_id='verify.intake') != null && history.last('visit.sealed', node_id='verify.intake').outcome == 'completed'` |
| **Hook** | `on_examine` |

### `agent-receipt-sealed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.count('receipt.linked', visit_id=visit.id, schema='registry:schemas/agent-receipt.schema.json') >= 1` |
| **Hook** | `on_seal` |

## Gaps

- production pass requires future bounded validator evidence; stub env FOUNDRY_VERIFY_ACCEPTANCE_DECISION=pass for integration only
- diff text never counts as proof of behavioral AC satisfaction

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
| **id** | `verify.acceptance` |
| **kind** | `step` |
| **title** | Automated acceptance criteria validation |
