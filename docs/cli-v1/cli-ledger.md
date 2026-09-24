# ledger

Status: **draft capability spec**

The `foundry ledger` command group reads the append-only event sequence for a run. The ledger is the authoritative audit source per [run-record.md](../workflow-schema-v1/run-record.md); the state snapshot is derived and may lag until resume. `ledger query` evaluates `history.*` expressions from [expressions.md](../workflow-schema-v1/expressions.md) against the same event stream checks and connection conditions use.

---

## show

### Purpose

Return the full ledger or a bounded slice for a run. Primary auditor and debugger view of immutable workflow history.

### Who invokes

| Actor | When |
|---|---|
| operator | Forensic review of a run |
| steward | Inspect prior decisions and seals |
| eval | Harness compares expected event sequences |
| engine | Internal replay (CLI exposes the same read API) |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--from-seq` | no | First sequence number (inclusive, default: 1) |
| `--to-seq` | no | Last sequence number (inclusive) |
| `--types` | no | Comma-separated event type filter |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry ledger show --run run-2026-09-24-porcelain-003 --from-seq 40 --to-seq 55 --json
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "events": [
    {
      "seq": 42,
      "at": "2026-09-23T22:01:04Z",
      "run_id": "run-2026-09-24-porcelain-003",
      "visit_id": "v-003",
      "node_id": "shape.present",
      "type": "lifecycle.changed",
      "payload": {"from": "closed", "to": "sealed"}
    },
    {
      "seq": 43,
      "at": "2026-09-23T22:01:05Z",
      "visit_id": "v-003",
      "node_id": "shape.present",
      "type": "visit.sealed",
      "payload": {"outcome": "completed", "reason": null}
    },
    {
      "seq": 44,
      "at": "2026-09-23T22:01:05Z",
      "visit_id": "v-003",
      "node_id": "shape.present",
      "type": "connection.taken",
      "payload": {"connection_id": "shape.present-to-shape.record", "to_node_id": "shape.record"}
    }
  ],
  "truncated": false
}
```

### Ledger events appended

None (read-only).

### Related factory-flow.yaml nodes/checks

All nodes; event ordering rules in [run-record.md](../workflow-schema-v1/run-record.md) apply to every transition (e.g. `visit.sealed` before `connection.taken` on `shape.present`).

### Cross-links

- [cli-run.md](cli-run.md) — `resume` rebuilds state from this stream
- [cli-ledger.md](cli-ledger.md) — `query` for expression evaluation
- [expressions.md](../workflow-schema-v1/expressions.md) — `history.*` function definitions

---

## tail

### Purpose

Stream or fetch the most recent ledger events. Useful for watching an active run or attaching to long-running build steps.

### Who invokes

| Actor | When |
|---|---|
| steward | Monitor progress during `execute.build` |
| operator | Live audit during dogfood |
| eval | Poll until expected event appears |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--follow` | no | Block and emit new events as appended |
| `--limit` | no | Maximum events to return (default: 20) |
| `--types` | no | Comma-separated event type filter |
| `--json` | no | Emit machine-readable result (one event per line when following) |

### Sample invocation

```text
foundry ledger tail --run run-2026-09-24-porcelain-003 --limit 5 --json
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "events": [
    {
      "seq": 61,
      "type": "check.recorded",
      "node_id": "execute.test",
      "payload": {"check": "agent-receipt-sealed", "result": "pass"}
    },
    {
      "seq": 62,
      "type": "policy.applied",
      "node_id": "execute.test",
      "payload": {"check": "agent-receipt-sealed", "action": "continue"}
    },
    {
      "seq": 63,
      "type": "lifecycle.changed",
      "node_id": "execute.test",
      "payload": {"from": "closed", "to": "sealed"}
    },
    {
      "seq": 64,
      "type": "visit.sealed",
      "node_id": "execute.test",
      "payload": {"outcome": "completed"}
    },
    {
      "seq": 65,
      "type": "connection.taken",
      "payload": {"connection_id": "execute.test-to-execute.test.gate", "to_node_id": "execute.test.gate"}
    }
  ]
}
```

### Ledger events appended

None (read-only).

### Related factory-flow.yaml nodes/checks

Recent activity on active nodes such as `execute.build`, `execute.test`, `verify.acceptance`.

### Cross-links

- [cli-ledger.md](cli-ledger.md) — `show` for full history
- [cli-run.md](cli-run.md) — `show` for summarized position

---

## query

### Purpose

Evaluate `history.*` expressions from [expressions.md](../workflow-schema-v1/expressions.md) against the run ledger. Side-effect free; mirrors check `when` bodies and connection conditions that read history.

### Who invokes

| Actor | When |
|---|---|
| engine | Dry-run check evaluation (see [cli-gate.md](cli-gate.md) `evaluate`) |
| eval | Assert loop limits, gate decisions, receipt counts |
| operator | Ad-hoc audit queries |
| steward | Debug why a connection or check blocked |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--expr` | yes | History expression to evaluate |
| `--visit` | no | Bind `visit.*` namespace to a specific visit id |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry ledger query --run run-2026-09-24-porcelain-003 --expr "history.count('connection.taken', loop='reshape')" --json
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "expression": "history.count('connection.taken', loop='reshape')",
  "value": 0,
  "error": null
}
```

Additional examples tied to factory-flow checks:

```text
foundry ledger query --run RUN --expr "history.last('visit.sealed', node_id='shape.intake').outcome == 'completed'"
foundry ledger query --run RUN --visit v-010 --expr "history.count('receipt.linked', visit_id=visit.id, schema='registry:schemas/intake-receipt.schema.json') >= 1"
foundry ledger query --run RUN --expr "history.last('gate.resolved', node_id='verify.acceptance.gate').decision == 'pass'"
```

### Ledger events appended

None (read-only).

### Related factory-flow.yaml nodes/checks

| Check | Expression pattern |
|---|---|
| `prior-shape-intake-sealed` | `history.last('visit.sealed', node_id='shape.intake')` |
| `reshape-within-limit` | `history.count('connection.taken', loop='reshape')` |
| `intake-receipt-sealed` | `history.count('receipt.linked', visit_id=visit.id, ...)` |
| `acceptance-passed` | `history.last('gate.resolved', node_id='verify.acceptance.gate')` |
| `reverify-within-limit` | sealed `verify.intake` visit count |

### Cross-links

- [expressions.md](../workflow-schema-v1/expressions.md) — grammar and `history.*` functions
- [cli-gate.md](cli-gate.md) — `evaluate` uses the same evaluator
- [cli-run.md](cli-run.md) — `integrity-check` bundles common queries
- [control-plane.md](../workflow-schema-v1/control-plane.md) — history-backed checks
