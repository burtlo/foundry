# Node: `verify.code_review`

Status: **ok**

Flow: `implementation` in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

Host-owned deterministic review packet after code quality gate pass or code_quality skip. Publishes verify-notes.md, patches verify_notes state, routes to verify.code_review.gate for human accept, reject, or reshape.


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

  sealed --> [*]: connection.taken\n→ verify.code_review.gate
  sealed --> opened: reopen\n(same visit_id)
```

| Hook | Authored checks | Engine-implicit |
|---|---|---|
| `on_examine` | `acceptance-passed`, `code-quality-done-or-skipped` | — |
| `on_open` | *(empty)* | — |
| `on_close` | *(empty)* | Declared artifact completeness |
| `on_seal` | *(empty)* | — |

## Sequence

```mermaid
sequenceDiagram
  autonumber
  participant S as Steward
  participant CLI as foundry CLI
  participant E as Engine

  Note over S,E: After verify.code_quality.gate pass or code_quality not_applicable
  CLI->>E: admit verify.code_review, on_examine checks
  CLI->>E: run advance (opened) → run_verify_code_review_complete
  E->>E: publish verify-notes.md, patch verify_notes
  E->>E: transition → verify.code_review.gate
  Note over S,E: Human accept / reject / reshape at user gate only
```

## References

- **Catalog index:** [verify.code_review.index.yaml](../../.cursor/foundry/catalog/nodes/verify.code_review.index.yaml)

## Ownership

| Role | Owner |
|---|---|
| **worker** | none |
| **steward** | verify parent / craft steward — use run advance only; do not manually publish verify-notes |
| **engine** | on_examine acceptance-passed + code-quality-done-or-skipped; run_verify_code_review_complete via run advance |

## Permissions

### `reads`

| Namespace | Paths |
|---|---|
| `state` | `approved_ac`, `verify_findings`, `branch_diff_artifact_path` |
| `artifacts` | `verify.intake.branch-diff`, `verify.acceptance.verify-findings` |

### `allow`

| Namespace | Grant | Purpose |
|---|---|---|
| — | *(none declared)* | — |

### Engine-only surfaces

| Surface | Trigger | Maps to |
|---|---|---|
| `foundry run create` | New run bootstrap | Admit entry visit, run `on_open` |
| `acceptance-passed` | `on_examine` hook | `on_examine` check `acceptance-passed` |
| `code-quality-done-or-skipped` | `on_examine` hook | `on_examine` check `code-quality-done-or-skipped` |
| Artifact completeness | `close_request` before `closed` | Every `produces.artifacts` declaration satisfied |
| Connection selection | After `visit.sealed` | Routes to `verify.code_review.gate` |

## Artifacts

### Work artifact: `verify-notes`

| Field | Value |
|---|---|
| **Logical id** | `verify-notes` |
| **Qualified ref** | `verify.code_review.verify-notes` |
| **Kind** | `document` |
| **URI** | `run:artifacts/{visit_id}/verify-notes.md` |
| **Media type** | `text/markdown` |


## Receipts

_No receipts declared._

## Worker

_No worker bound._

## Connections

### Incoming

- `verify.code_quality-to-verify.code_review-skipped`: [verify.code_quality](verify.code_quality.md) → **verify.code_review**
- `verify.code_quality.gate-to-verify.code_review-pass`: [verify.code_quality.gate](verify.code_quality.gate.md) → **verify.code_review**

### Outgoing

- `verify.code_review-to-verify.code_review.gate`: **verify.code_review** → [verify.code_review.gate](verify.code_review.gate.md) (`on.outcomes: ['completed']`)

## Check catalog

### `acceptance-passed`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `history.last('gate.resolved', node_id='verify.acceptance.gate') != null && history.last('gate.resolved', node_id='verify.acceptance.gate').decision == 'pass'` |
| **Hook** | `on_examine` |

### `code-quality-done-or-skipped`

| Property | Value |
|---|---|
| **Body** | `when` |
| **Expression** | `!config.review.enabled || (history.last('visit.sealed', node_id='verify.code_quality') != null && history.last('visit.sealed', node_id='verify.code_quality').outcome in ['completed', 'not_applicable'])` |
| **Hook** | `on_examine` |

## Gaps

- verify-notes content is a minimal host stub; richer diff/AC synthesis is future work

## Concepts

- **Lifecycle:** [Visit lifecycle](../concepts/visits-lifecycle.md)
- **Connections:** [Graph and routing](../concepts/graph.md)
- **Permissions:** [Reads and allow](../concepts/capabilities.md)
- **Artifacts:** [Artifact publication](../concepts/artifacts.md)
- **Checks:** [Control plane](../concepts/control-plane.md)

## Node summary

| Field | Value |
|---|---|
| **id** | `verify.code_review` |
| **kind** | `step` |
| **title** | Human code review — single turn |
