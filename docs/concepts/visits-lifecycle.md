# Visits and lifecycle

A **visit** is one passage through a [node](graph.md#nodes). This document covers the visit model, [lifecycle states](#lifecycle-states), [hook timing](#hook-timing), [seal outcomes](#seal-outcomes), and the distinction between closed and sealed. For declared outputs and publication, see [artifacts.md](artifacts.md). For check evaluation at hooks, see [control-plane.md](control-plane.md). For ledger recording, see [run-record.md](run-record.md).

---

## Visit model

A visit is one passage through a node:

```yaml
visit:
  id: v-003
  node_id: shape.examine
  kind: step
  lifecycle: opened
  outcome: null
  decision: null
  outputs: {}
  routed_from_visit_id: v-002
  routed_by_connection_id: present-to-examine
```

The visit id remains stable from admission through seal. Routing to any node, including the same node, creates a new visit id.

### Lifecycle states

| State | Meaning | Responsible actor |
|---|---|---|
| `examined` | Visit exists and is being evaluated for eligibility | Engine |
| `opened` | Work or decision interaction is in progress | Steward |
| `closed` | Steward claims the declared output is ready | Steward |
| `sealed` | Engine has accepted the visit's final disposition | Engine |

Normal progression is:

```text
admit → examined → opened → closed → sealed
```

Admission is an event, not a lifecycle state.

`closed` and `sealed` are deliberately different:

- **Closed:** the steward claims completion.
- **Sealed:** the engine has verified and accepted the claim.

### Hook timing

Hooks run at precise points:

| Hook | Current state | Purpose | Successful continuation |
|---|---|---|---|
| `on_examine` | `examined` | Determine whether this visit applies | Run `on_open` |
| `on_open` | `examined` | Verify prerequisites for steward work | Enter `opened` |
| `on_close` | `opened` | Validate the steward's close request | Enter `closed` |
| `on_seal` | `closed` | Verify output and evidence | Enter `sealed` |

An omitted or empty hook succeeds.

The steward acts only while the visit is `opened`. The engine runs all checks.

The `on_` prefix identifies these fields as lifecycle hooks rather than lifecycle states. Each hook runs when the engine reaches that lifecycle point and before the successful continuation shown above. In v1, a hook is directly an ordered list of check references; there is no nested `checks` key.

### Seal outcomes

| Outcome | Meaning |
|---|---|
| `completed` | Declared work or decision was accepted |
| `not_applicable` | The node did not apply to this visit |
| `disqualified` | Policy ruled the node out |

An outcome exists only when the visit is sealed. A failed check is not a seal outcome; policy decides whether the run halts, pauses, reopens, or seals with another outcome.
