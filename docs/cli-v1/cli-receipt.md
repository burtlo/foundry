# receipt

Status: **draft capability spec**

The `foundry receipt` command group seals worker evidence files under the run receipt area. Receipts are engine-recorded proof of how work was performed — distinct from declared work artifacts per [artifacts.md](../workflow-schema-v1/artifacts.md#receipts-are-evidence). Sealing validates against schema paths listed on the node's `receipts` field and appends `receipt.linked` per [run-record.md](../workflow-schema-v1/run-record.md).

---

## seal

### Purpose

Validate a receipt payload, store it at an engine-assigned path under the run receipt area, and link it in the ledger. Builders do not invent receipt ids or durable filenames; the CLI combines steward/worker payload with engine-owned provenance.

Often invoked via `visit transition --receipt` or automatically when the worker contract defines a completion payload.

### Who invokes

| Actor | When |
|---|---|
| steward | Step completion before `transition` |
| engine | Proxy when worker tool completes via contract |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--visit` | no | Visit id (default: active visit) |
| `--schema` | no | Receipt schema path (default: sole entry from node `receipts`) |
| `--file` | yes* | `run:` or `workspace:` path to receipt JSON (*or stdin via `--stdin`) |
| `--stdin` | no | Read receipt JSON from stdin |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry receipt seal --run run-2026-09-24-porcelain-003 --visit v-001 --schema registry:schemas/intake-receipt.schema.json --file workspace:.foundry/tmp/intake-receipt.json --json
```

### Sample JSON result

```json
{
  "receipt_id": "rcpt-v-001-intake",
  "path": "run:receipts/v-001/intake-receipt.json",
  "schema": "registry:schemas/intake-receipt.schema.json",
  "visit_id": "v-001",
  "node_id": "shape.intake",
  "ledger_seq": 11
}
```

### Ledger events appended

| Event | Payload |
|---|---|
| `receipt.linked` | `receipt_id`, `path`, `schema` (full registry path) |

`schema` MUST match the canonical value from the node's `receipts` list (e.g. `registry:schemas/intake-receipt.schema.json`). Checks such as `intake-receipt-sealed` and `agent-receipt-sealed` filter on this exact string.

Must precede `on_seal` checks that require receipt evidence per [run-record.md](../workflow-schema-v1/run-record.md) ordering.

### Related factory-flow.yaml nodes/checks

| Node | Receipt schemas | Sealing check |
|---|---|---|
| `shape.intake` | `agent-receipt`, `intake-receipt` | `agent-receipt-sealed`; gate: `intake-receipt-sealed` |
| `shape.examine` | `agent-receipt` | `agent-receipt-sealed` on `on_seal` |
| `shape.present` | `agent-receipt` | `agent-receipt-sealed` → `reopen` on fail |
| `shape.record` | `agent-receipt` | `agent-receipt-sealed` |
| `execute.intake` | `agent-receipt`, `intake-receipt` | `intake-receipt-sealed` on `execute.intake.gate` |
| `execute.plan` | `agent-receipt` | `agent-receipt-sealed` |
| `execute.build` | `agent-receipt` | `agent-receipt-sealed`; may include commit SHA from `--commit` |
| `execute.test` | `agent-receipt` | `agent-receipt-sealed` |
| `execute.commit` | `agent-receipt` | `agent-receipt-sealed` |
| `verify.intake` | `agent-receipt`, `intake-receipt` | `intake-receipt-sealed` on `verify.intake.gate` |
| `verify.acceptance` | `agent-receipt` | `agent-receipt-sealed` |
| `verify.code_quality` | `agent-receipt` | `agent-receipt-sealed` |

### Cross-links

- [cli-visit.md](cli-visit.md) — `transition --receipt` and `on_seal` hook chain
- [cli-ledger.md](cli-ledger.md) — `history.count('receipt.linked', ...)`
- [cli-run.md](cli-run.md) — `integrity-check` receipt suite
- [artifacts.md](../workflow-schema-v1/artifacts.md) — receipts vs artifacts distinction
