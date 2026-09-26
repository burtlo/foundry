# run

Status: **draft capability spec**

The `foundry run` command group manages run identity, lifecycle, steward handoffs, and eval harness integrity. Runs persist an append-only event ledger, mutable state snapshot, artifact store, and receipt files as defined in [run-record.md](../workflow-schema-v1/run-record.md). The engine admits visits and appends ledger events per [engine.md](../workflow-schema-v1/engine.md). Resume and integrity checks rebuild or validate against that authoritative sequence.

---

## create

### Purpose

Create a new run, admit the flow entry visit (`shape.intake` in the implementation flow), and initialize the ledger plus state snapshot. Equivalent to bootstrapping a `/craft-shape` session with a durable run id.

### Who invokes

| Actor | When |
|---|---|
| steward | User starts shape or execute with a non-shaped external plan |
| operator | Manual run bootstrap for testing |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--flow` | no | Flow id (default: `implementation`) |
| `--run-dir` | no | Override run directory root |
| `--ticket` | no | Path to initial ticket input (`workspace:` or `run:`) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry run create --flow implementation --json
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "flow_id": "implementation",
  "status": "running",
  "entry_node_id": "shape.intake",
  "active_visit_id": "v-001",
  "run_dir": "run:.foundry/runs/run-2026-09-24-porcelain-003"
}
```

### Ledger events appended

| Event | When |
|---|---|
| `visit.admitted` | Entry visit created at `shape.intake` |
| `lifecycle.changed` | `examined` after admission; `opened` after `on_examine` and `on_open` succeed |
| `run.status_changed` | Initial `running` status recorded |

### Related factory-flow.yaml nodes/checks

| Node / check | Role |
|---|---|
| `flow.entry: shape.intake` | First admitted visit |
| `validate-manifest` | `on_open` on `shape.intake` |

### Cross-links

- [cli-visit.md](cli-visit.md) — `transition` closes the admitted visit after steward work
- [cli-ledger.md](cli-ledger.md) — authoritative audit trail from creation
- [cli-gate.md](cli-gate.md) — user gates after shape steps

---

## show

### Purpose

Display run position, phase/step visualization, decisions, repairs, reroutes, and summation. Product equivalent of `/craft-status`.

### Who invokes

| Actor | When |
|---|---|
| steward | Resume context in chat |
| operator | Inspect run without mutating state |
| eval | Harness assertions on position |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id or `run:` path (*default: current run in cwd) |
| `--phase` | no | Filter visualization to one phase (`shape`, `execute`, `verify`) |
| `--verbose` | no | Include sealed visit summaries and loop classifications |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry run show --run run-2026-09-24-porcelain-003 --json
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "status": "running",
  "phase": "shape",
  "active_visit": {
    "id": "v-004",
    "node_id": "shape.examine",
    "lifecycle": "opened"
  },
  "last_sealed": {
    "visit_id": "v-003",
    "node_id": "shape.intake",
    "outcome": "completed"
  },
  "pending_gate": null,
  "loop_counts": {
    "reshape": 0,
    "repair": 0,
    "reexecute": 0,
    "reverify": 0
  },
  "summation": "Shape examination in progress; 2 open clarifying questions."
}
```

### Ledger events appended

None (read-only).

### Related factory-flow.yaml nodes/checks

Reflects current position among all implementation-flow nodes (`shape.*`, `execute.*`, `verify.*`, `deliver.stub`).

### Cross-links

- [cli-ledger.md](cli-ledger.md) — raw event history behind the summary
- [cli-visit.md](cli-visit.md) — active visit detail
- [cli-escalation.md](cli-escalation.md) — when `status` is `paused`

---

## context

### Purpose

Emit the steward context packet for the active visit: reads resolution, capability grants, artifact declarations, worker binding, instructions path, and resolved file paths. Used when opening or continuing a phase chat (see [instructions.md](../../.cursor/foundry/nodes/shape.intake/instructions.md)).

**Acceptance features:** [run_context.feature](acceptance/features/run_context.feature) (pytest-bdd runner: [acceptance/README.md](acceptance/README.md))

**JSON Schema:** [context-packet.schema.json](../../.cursor/foundry/schemas/context-packet.schema.json)

**Implementation:** `.cursor/foundry/cli/foundry.py`

### Who invokes

| Actor | When |
|---|---|
| steward | Parent agent loads step context |
| engine | Internal context assembly (CLI exposes same view) |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--visit` | no | Visit id (default: active visit) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry run context --run run-2026-09-24-porcelain-003 --json
```

### Sample JSON result

```json
{
  "ok": true,
  "context": {
    "run_id": "porcelain-0007",
    "visit_id": "v-001",
    "node_id": "shape.intake",
    "kind": "step",
    "lifecycle": "opened",
    "title": "Shape intake — validates inputs, prerequisites, and configuration",
    "reads": {
      "config": { "workspace": "/path/to/app" },
      "state": { "ticket": null, "app_folder": null },
      "artifacts": [],
      "files": []
    },
    "allow": {
      "cli": ["artifact.publish", "receipt.link", "transition"],
      "state": ["ticket", "app_folder", "state.nodes.shape.intake.*"],
      "files": {
        "write": [
          { "uri": "run:ticket.json", "resolved_path": "/path/to/run/ticket.json" },
          { "uri": "run:artifacts/v-001/ticket.json", "resolved_path": "/path/to/run/artifacts/v-001/ticket.json" }
        ]
      },
      "agents": [],
      "user": { "ask": false, "decide": false }
    },
    "produces": {
      "artifacts": [
        {
          "id": "ticket",
          "kind": "document",
          "uri": "run:artifacts/{visit_id}/ticket.json",
          "resolved_uri": "run:artifacts/v-001/ticket.json",
          "schema": "registry:schemas/ticket.schema.json",
          "media_type": "application/json"
        }
      ],
      "options": []
    },
    "worker": {
      "prompt": "registry:agents/intake-checker.shape.md",
      "contract": "registry:workers/intake-checker.shape/contract.yaml",
      "mode": "shape",
      "prompt_path": "/path/to/.cursor/agents/intake-checker.shape.md",
      "contract_path": "/path/to/.cursor/foundry/workers/intake-checker.shape/contract.yaml"
    },
    "receipts": [
      "registry:schemas/agent-receipt.schema.json",
      "registry:schemas/intake-receipt.schema.json"
    ],
    "instructions": "registry:nodes/shape.intake/instructions.md",
    "instructions_path": "/path/to/.cursor/foundry/nodes/shape.intake/instructions.md"
  }
}
```

### Ledger events appended

None (read-only).

### Related factory-flow.yaml nodes/checks

Node-local `reads`, `allow`, `worker`, `receipts`, and `instructions` for the active visit (e.g. `shape.examine`, `execute.build`).

### Cross-links

- [capabilities.md](../workflow-schema-v1/capabilities.md) — read and allow semantics
- [artifacts.md](../workflow-schema-v1/artifacts.md) — declared `produces` and resolved reads
- [cli-visit.md](cli-visit.md) — lifecycle state of the visit

---

## resume

### Purpose

Rebuild the state snapshot from the authoritative ledger and continue execution. Supports phase-filtered resume packets for `/craft-resume` in a fresh chat.

### Who invokes

| Actor | When |
|---|---|
| steward | `/craft-resume` after chat switch |
| engine | Recovery after crash between ledger append and snapshot write |
| operator | Manual resume after halt |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--phase` | no | Limit resume packet to `shape`, `execute`, or `verify` |
| `--rebuild-only` | no | Rebuild snapshot without advancing execution |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry run resume --run run-2026-09-24-porcelain-003 --phase execute --json
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "status": "running",
  "rebuilt_from_seq": 87,
  "active_visit": {
    "id": "v-012",
    "node_id": "execute.intake",
    "lifecycle": "opened"
  },
  "resume_packet": {
    "phase": "execute",
    "plan_path": "run:plan.md",
    "approved_ac_version": 1,
    "pending_actions": ["complete execute.intake intake receipt", "transition when ready"]
  }
}
```

### Ledger events appended

None during rebuild. Subsequent steward or engine actions append events per [run-record.md](../workflow-schema-v1/run-record.md) ordering.

### Related factory-flow.yaml nodes/checks

Resume position is the last non-terminal visit in ledger order. Phase filter maps node id prefixes (`shape.`, `execute.`, `verify.`).

### Cross-links

- [cli-run.md](cli-run.md) — `show` for human-readable position
- [cli-ledger.md](cli-ledger.md) — source of truth for rebuild
- [engine.md](../workflow-schema-v1/engine.md) — snapshot/ledger atomicity

---

## handoff

### Purpose

End the current steward turn without closing the visit. Records handoff metadata (summary, paths, pending gates) for the next chat or operator while the visit remains `opened`.

### Who invokes

| Actor | When |
|---|---|
| steward | Phase chat ends mid-step (e.g. before `transition`) |
| operator | Force context switch without abandoning work |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--summary` | no | Short steward-written handoff note |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry run handoff --run run-2026-09-24-porcelain-003 --summary "Examination round 2 complete; 1 open question on auth scope."
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "visit_id": "v-004",
  "node_id": "shape.examine",
  "lifecycle": "opened",
  "handoff_recorded_at": "2026-09-24T14:22:01Z",
  "resume_hint": "foundry run resume --phase shape"
}
```

### Ledger events appended

Implementations MAY append a run-scoped handoff annotation event; v1 minimum is state snapshot update with `last_handoff` metadata. No lifecycle change.

### Related factory-flow.yaml nodes/checks

Any `opened` step visit (e.g. `shape.examine`, `execute.build`, `verify.code_review`).

### Cross-links

- [cli-run.md](cli-run.md) — `resume` consumes handoff packet
- [cli-visit.md](cli-visit.md) — visit stays `opened` until `transition`

---

## abandon

### Purpose

Intentionally stop a run without sealing the active visit. Sets durable status so the run cannot proceed without operator intervention.

### Who invokes

| Actor | When |
|---|---|
| steward | User aborts examination or mid-phase work |
| operator | Discard a test or corrupted run |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--reason` | yes | Non-empty abandonment reason |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry run abandon --run run-2026-09-24-porcelain-003 --reason "User cancelled shape examination."
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "prior_status": "running",
  "status": "halted",
  "active_visit_id": "v-004",
  "abandoned_at": "2026-09-24T14:30:00Z"
}
```

### Ledger events appended

| Event | When |
|---|---|
| `run.status_changed` | `running` → `halted` with abandonment reason |

No `visit.sealed` on the active visit.

### Related factory-flow.yaml nodes/checks

Any active non-terminal visit. Does not select a connection.

### Cross-links

- [cli-run.md](cli-run.md) — `recover` for operator-led restart from halt
- [control-plane.md](../workflow-schema-v1/control-plane.md) — `halt` action semantics

---

## recover

### Purpose

Return a halted or errored run to a resumable position after operator review. Does not bypass checks or seal visits automatically.

### Who invokes

| Actor | When |
|---|---|
| operator | Resume after `abandon`, policy `halt`, or `execution_error` |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--reason` | yes | Operator reason for recovery |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry run recover --run run-2026-09-24-porcelain-003 --reason "False positive on git clean check; tree corrected."
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "prior_status": "halted",
  "status": "running",
  "active_visit_id": "v-008",
  "node_id": "execute.intake",
  "lifecycle": "opened",
  "recovered_at": "2026-09-24T15:01:00Z"
}
```

### Ledger events appended

| Event | When |
|---|---|
| `run.status_changed` | `halted` or `execution_error` → `running` |

### Related factory-flow.yaml nodes/checks

Resumes at the same visit and hook position recorded before halt (e.g. `execute.intake` with `validate-git-clean-execute` failure).

### Cross-links

- [cli-run.md](cli-run.md) — `resume` for steward packet after recovery
- [cli-escalation.md](cli-escalation.md) — distinct from `paused` escalation resolution

---

## integrity-check

### Purpose

Eval harness command that validates run integrity without mutating workflow state. Checks ledger ordering, required events, receipt and artifact completeness, phase transitions, reroute counters, and capture invariants per [v1-spec.md](../v1-spec.md) eval harness.

### Who invokes

| Actor | When |
|---|---|
| eval | CI and porcelain dogfood harness |
| operator | Pre-merge or debug audit |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--suite` | no | Subset: `receipts`, `transitions`, `artifacts`, `loops`, `capture`, `all` (default: `all`) |
| `--dry-run` | no | Report only; same as default (no mutations) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry run integrity-check --run run-2026-09-24-porcelain-003 --suite all --json
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "passed": true,
  "checks": [
    {"id": "ledger-ordering", "passed": true},
    {"id": "intake-receipts", "passed": true, "nodes": ["shape.intake", "execute.intake", "verify.intake"]},
    {"id": "agent-receipts", "passed": true},
    {"id": "final-commit-recorded", "passed": true, "node_id": "execute.commit"},
    {"id": "reshape-loop-limit", "passed": true, "count": 0, "limit": 2},
    {"id": "examination-capture", "passed": true}
  ],
  "failures": []
}
```

### Ledger events appended

None (read-only probe).

### Related factory-flow.yaml nodes/checks

| Area | Checks / nodes |
|---|---|
| Intake receipts | `intake-receipt-sealed` on `*.intake.gate` nodes |
| Agent receipts | `agent-receipt-sealed` on sealed steps |
| Final commit | `final-commit-recorded`, `execute.commit` / `execute.commit.gate` |
| Loop limits | `repair-within-limit`, `reverify-within-limit` |
| Gate audit | `gate.presented` / `gate.resolved` pairs on all gates |

### Cross-links

- [cli-ledger.md](cli-ledger.md) — `query` for targeted history assertions
- [cli-receipt.md](cli-receipt.md) — receipt sealing invariants
- [cli-artifact.md](cli-artifact.md) — artifact publication completeness
- [validation.md](../workflow-schema-v1/validation.md) — structural vs semantic validation

---

For CLI mechanics borrowed from earlier prototypes, see [cli-poc-transition.md](cli-poc-transition.md).
