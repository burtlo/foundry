# Node: `verify.code_quality.gate`

Status: **ok**

Flow: `implementation` in [flows/implementation/registry.yaml](../../.cursor/foundry/flows/implementation/registry.yaml).

Engine gate after verify.code_quality when the step is sealed completed. The host or steward uses run advance to resolve pass (all command exit codes zero, receipt not failed) or repair from the implementation-validator agent receipt. No user gate decide and no worker.

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

  closed --> sealed: on_seal\n(none)
  note right of sealed
    checks pass → sealed, outcome completed
    fail → reopen (closed → opened)
  end note

  sealed --> [*]: connection.taken\n→ verify.code_review, execute.repair.limit.gate
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `code-quality-done-or-skipped` | — |
| `on_open` | *(empty)* | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | *(empty)* | — |

## Sequence

_Sequence diagram not authored in `doc.yaml`._

## References

- **Gate prompt:** `Route passing code-quality results to human review and failed results to execution repair.`
- **Catalog index:** [verify.code_quality.gate.index.yaml](../catalog/implementation/nodes/verify.code_quality.gate.index.yaml)

## Permissions

### `reads`

| Namespace | Paths |
|---|---|
| — | *(none declared)* |

### `allow`

| Namespace | Grant | Purpose |
|---|---|---|
| — | *(none declared)* | — |

### Engine-only surfaces

| Surface | Trigger | Maps to |
|---|---|---|
| `foundry run create` | New run bootstrap | Admit entry visit, run `on_open` |
| `code-quality-done-or-skipped` | `on_examine` hook | `on_examine` check `code-quality-done-or-skipped` |
| Artifact completeness | `close_request` before `closed` | Every `produces.artifacts` declaration satisfied |
| Connection selection | After `visit.sealed` | Routes to `verify.code_review`, `execute.repair.limit.gate` |

## Artifacts

_No work artifacts declared._

## Receipts

_No receipts declared._

## Connections

### Incoming

- `verify.code_quality-to-verify.code_quality.gate`: [verify.code_quality](verify.code_quality.md) → **verify.code_quality.gate**

### Outgoing

- `verify.code_quality.gate-to-verify.code_review-pass`: **verify.code_quality.gate** → [verify.code_review](verify.code_review.md) (`on.outcomes: ['completed']`)
- `verify.code_quality.gate-to-execute.repair.limit.gate-repair`: **verify.code_quality.gate** → [execute.repair.limit.gate](execute.repair.limit.gate.md) (`on.outcomes: ['completed']`)

## Check catalog

### `code-quality-done-or-skipped`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `!config.review.enabled || (history.last('visit.sealed', node_id='verify.code_quality') != null && history.last('visit.sealed', node_id='verify.code_quality').outcome in ['completed', 'not_applicable'])` |
| **Hook** | `on_examine` |

## Concepts

- **Lifecycle:** [Visit lifecycle](../concepts/visits-lifecycle.md)
- **Connections:** [Graph and routing](../concepts/graph.md)
- **Checks:** [Control plane](../concepts/control-plane.md)
- **Gate decisions:** [Gate nodes](../concepts/graph.md)

## Node summary

| Field | Value |
|---|---|
| **id** | `verify.code_quality.gate` |
| **kind** | `gate` |
| **title** | Code quality result routing |
