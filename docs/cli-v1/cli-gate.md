# gate

Status: **draft capability spec**

The `foundry gate` command group records gate decisions and dry-runs engine gate evaluation. Gates produce a `visit.decision` from `produces.options` per [graph.md](../workflow-schema-v1/graph.md). User gates (`decider: user`) close via `gate decide`; engine gates (`decider: engine`) auto-resolve when hook checks determine the outcome. Presentation and resolution append `gate.presented` and `gate.resolved` per [run-record.md](../workflow-schema-v1/run-record.md).

---

## decide

### Purpose

Record the authorized decision on an `opened` user gate and request close. This **is** the gate close request — equivalent to `visit transition` for steps but constrained to declared options.

### Who invokes

| Actor | When |
|---|---|
| steward | Human selects among gate options (plugin `/craft-*` CTAs) |
| operator | Manual decision in dogfood |

Not valid on `decider: engine` gates.

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--visit` | no | Visit id (default: active gate visit) |
| `--decision` | yes | One of the gate's `produces.options` |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry gate decide --run run-2026-09-24-porcelain-003 --decision present --json
```

### Sample JSON result

```json
{
  "visit_id": "v-004",
  "node_id": "shape.examine.gate",
  "decision": "present",
  "lifecycle": "sealed",
  "outcome": "completed",
  "connection": {
    "connection_id": "shape.examine.gate-to-shape.present-present",
    "to_node_id": "shape.present"
  },
  "next_visit_id": "v-005"
}
```

### Ledger events appended

| Order | Event |
|---|---|
| 1 | `gate.presented` (if not already appended at admission) |
| 2 | `gate.resolved` with `decision` |
| 3+ | Hook checks: `check.recorded`, `policy.applied` |
| n | `lifecycle.changed`, `visit.sealed` |
| n+1 | `connection.taken` matching `on.decisions` |

If `on_seal` policy `reopen` fires on a gate, `visit.decision` is cleared; a new `gate.resolved` is required before re-close per [control-plane.md](../workflow-schema-v1/control-plane.md).

### Related factory-flow.yaml nodes/checks

| Gate node | Options | Decider |
|---|---|---|
| `shape.examine.gate` | `present`, `continue` | user |
| `shape.present.gate` | `refine`, `record` | user |
| `shape.record.gate` | `record` | user |
| `execute.start` | `start` | user |
| `verify.code_review.gate` | `approve`, `reshape`, `repair` | user |
| `verify.complete.gate` | `complete` | user |

### Cross-links

- [cli-visit.md](cli-visit.md) — step close via `transition`
- [cli-ledger.md](cli-ledger.md) — query `history.last('gate.resolved', ...)`
- [artifacts.md](../workflow-schema-v1/artifacts.md) — gate accountable output is `visit.decision`

---

## evaluate

### Purpose

Dry-run engine gate evaluation without mutating workflow state. Runs the gate's `on_examine` (and admission) checks, computes the auto decision for `decider: engine` gates, and reports which connection would be eligible. For testing and eval harness per [v1-spec.md](../v1-spec.md).

### Who invokes

| Actor | When |
|---|---|
| eval | Harness verifies routing logic before live run |
| engine | Pre-flight validation (CLI exposes same evaluator) |
| operator | Debug why an engine gate blocked or routed |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--node` | yes | Gate node id to evaluate |
| `--visit` | no | Hypothetical visit context (default: simulate next admission) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry gate evaluate --run run-2026-09-24-porcelain-003 --node execute.test.gate --json
```

### Sample JSON result

```json
{
  "node_id": "execute.test.gate",
  "decider": "engine",
  "checks": [
    {"check": "prior-execute-test-sealed", "result": "pass", "action": "continue"}
  ],
  "auto_decision": "pass",
  "decision_source": "prior execute.test visit sealed with passing verification; no additional gate catalog checks",
  "eligible_connections": [
    {"connection_id": "execute.test.gate-to-execute.commit-pass", "to_node_id": "execute.commit", "on": {"decisions": ["pass"]}}
  ],
  "would_append": ["gate.presented", "gate.resolved", "visit.sealed", "connection.taken"],
  "mutated": false
}
```

### Engine gates (`decider: engine`)

All engine gates in the implementation flow and their auto decisions:

| Gate node | Options | Auto decision logic |
|---|---|---|
| `execute.intake.gate` | `pass` | `intake-receipt-sealed` pass → `pass`; fail policy → `halt` |
| `execute.test.gate` | `pass`, `repair` | Test verification exit → `pass` or `repair` |
| `execute.repair.limit.gate` | `proceed` | `repair-within-limit` pass → `proceed`; fail policy → `escalate` |
| `execute.commit.gate` | `pass` | `final-commit-recorded` + within `reverify-within-limit` → `pass` |
| `verify.intake.gate` | `pass` | `intake-receipt-sealed` pass → `pass` |
| `verify.acceptance.gate` | `pass`, `replan`, `reshape`, `rework_execute` | Acceptance validator outcome maps to decision |
| `verify.code_quality.gate` | `pass`, `repair` | Code quality step outcome or skip when review disabled |

Engine gates do not accept `gate decide` from stewards. The engine records `gate.resolved` with the computed decision when checks complete.

### Ledger events appended

None (`mutated: false`). Live execution appends `gate.presented` and `gate.resolved` as above.

### Related factory-flow.yaml nodes/checks

Engine gate checks including `prior-execute-test-sealed`, `intake-receipt-sealed`, `repair-within-limit`, `final-commit-recorded`, `reverify-within-limit`, `code-quality-done-or-skipped`, and acceptance routing checks on `verify.acceptance.gate`.

### Cross-links

- [cli-ledger.md](cli-ledger.md) — `query` for individual `history.*` probes
- [control-plane.md](../workflow-schema-v1/control-plane.md) — check results and policies
- [cli-run.md](cli-run.md) — `integrity-check` validates gate event pairs
