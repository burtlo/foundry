# Run record

The run has four complementary forms of persistence. This document defines run status, ledger events, and ordering. The engine procedure that appends events is in [engine.md](engine.md). History queries used by checks and connection conditions are in [expressions.md](expressions.md).

---

| Persistence | Responsibility |
|---|---|
| Event ledger | Authoritative sequence of workflow events |
| State snapshot | Mutable domain data and fast resume position |
| Artifact store | Immutable, per-visit documents and normalized external references |
| Receipt files | Authoritative worker outputs and evidence |

The ledger is append-only. State may summarize current position or mirror a current artifact, but it is not the audit source of truth. Artifact and receipt content remains in their stores; ledger events link each immutable item to its producing visit.

## Run status and outcome

The durable run status is one of:

| Status | Meaning | May resume? |
|---|---|:---:|
| `running` | A visit is active | yes |
| `paused` | An escalation awaits resolution | through escalation resolution |
| `halted` | Policy intentionally stopped execution | only through an explicit operator resume |
| `definition_error` | The registry or routing result is invalid | no; correct the definition |
| `execution_error` | A check or engine operation could not execute | only through an explicit operator retry |
| `completed` | A terminal visit sealed | no |

A completed run records a final outcome equal to the terminal visit's outcome: `completed`, `not_applicable`, or `disqualified`.

Every status change MUST append `run.status_changed`. A final terminal seal MUST append `run.completed` after `visit.sealed`. A halt, definition error, or execution error MUST be durable before control returns to the caller.

## Core ledger event

```yaml
seq: 42
at: 2026-09-23T22:01:04Z
run_id: run-2026-09-23-abc
visit_id: v-003
node_id: acceptance-review
type: connection.taken
payload:
  connection_id: review-approved
  to_node_id: verify.complete
```

`seq` is one-based and strictly increasing within a run. Events are immutable after append.

## Required event types

| Type | Required payload | Meaning |
|---|---|---|
| `visit.admitted` | source visit and connection ids, nullable for entry | A visit was created |
| `lifecycle.changed` | `from`, `to` | Visit lifecycle changed |
| `check.recorded` | hook, check id, result, output | A check observed reality |
| `check.errored` | hook, check id, error | A check could not be evaluated |
| `policy.applied` | check id, result, action, reason | A policy selected an action |
| `artifact.linked` | artifact id, producer visit id, URI, schema, media type, digest | A declared output was published |
| `visit.sealed` | outcome, reason, decision when present | A visit reached final disposition |
| `connection.taken` | connection id, target node id, optional loop classification | Routing selected one connection |
| `receipt.linked` | receipt id, path, schema | Evidence was attached |
| `gate.presented` | options, prompt reference | A gate was presented |
| `gate.resolved` | decision | A gate decision was recorded |
| `escalation.raised` | check id, reason | Execution paused |
| `escalation.resolved` | resolution, operator | Execution resumed or halted |
| `run.status_changed` | prior status, new status, reason | Durable run status changed |
| `run.completed` | terminal visit id and final outcome | The run ended at a terminal node |

Implementations MAY add event types, but MUST NOT change the meaning of these types.

For `receipt.linked`, `schema` is the full registry path declared in the node's `receipts` list, such as `registry:schemas/intake-receipt.schema.json`. Checks compare that canonical value rather than a schema basename.

## Event ordering

The engine MUST append events in this order:

1. `connection.taken` before the target `visit.admitted`;
2. `visit.admitted` before the visit's first `lifecycle.changed`;
3. `gate.presented` before `gate.resolved`;
4. `gate.resolved`, `artifact.linked`, and `receipt.linked` before the close request they support;
5. `check.recorded` before `policy.applied`;
6. `lifecycle.changed` to `sealed` before `visit.sealed`;
7. `visit.sealed` before `connection.taken` or `run.completed`;
8. `run.status_changed` before execution returns control because of a pause, halt, or error.

The engine MUST append the event before updating its state snapshot. It treats both writes as one logical operation; if a process stops between them, resume rebuilds the snapshot from the authoritative ledger.
