# Execute / Verify boundary audit

Generated from [`node_capability.audit_rows`](../../.cursor/foundry/cli/foundry_cli/engine/node_capability.py). Regenerate after engine changes (from `.cursor/foundry/cli`):

```sh
python -c "from pathlib import Path; from foundry_cli.registry import load_registry; from foundry_cli.engine.node_capability import audit_rows; b=Path('..').resolve(); _,f=load_registry(b); rows=audit_rows(f,b); print(rows)"
```

Host advancement behavior for nodes from `execute.start` through `deliver.stub`.

## Summary

| Status | Meaning |
| --- | --- |
| **gate-user** | User decision wait or `foundry start` at `execute.start` |
| **gate-engine** | Machine gate; checks declared in flow; host does not auto-complete routing |
| **implemented** | Host-owned step executor or task binding |
| **unsupported** | Operator wait (`unsupported:{node_id}`) — none expected on this path after workflow-02 skeleton |

## Per-node status

| Node | Status | Advance behavior |
| --- | --- | --- |
| `execute.start` | gate-user | Decision wait; `foundry start` records authorization and accepts gate |
| `execute.intake` | implemented | Host-owned step executor or task binding |
| `execute.intake.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `execute.branch` | implemented | Host-owned step executor or task binding |
| `execute.plan` | implemented | Host-owned step executor or task binding |
| `execute.build` | implemented | Host-owned step executor or task binding |
| `execute.test` | implemented | Host-owned step executor or task binding |
| `execute.test.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `execute.repair.limit.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `execute.commit` | implemented | Host-owned step executor or task binding |
| `execute.commit.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `verify.intake` | implemented | Host-owned step executor or task binding |
| `verify.intake.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `verify.acceptance` | implemented | Host-owned step executor or task binding |
| `verify.acceptance.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `verify.code_quality` | implemented | Host-owned step executor or task binding |
| `verify.code_quality.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `verify.code_review` | implemented | Host-owned step executor or task binding |
| `verify.code_review.gate` | gate-user | Decision wait; user `gate decide` / `decide` |
| `verify.complete` | implemented | Host-owned step executor or task binding |
| `verify.complete.gate` | gate-user | Decision wait; user `gate decide` / `decide` |
| `deliver.stub` | implemented | Host-owned step executor or task binding |

## Preserved contracts

- `execute.start` remains a user gate with explicit `foundry start` authorization (`execute.authorization.recorded`).
- Decision and `user_input` waits are unchanged for Shape and user gates.
- Agent waits remain where `tasks/{node_id}.yaml` exists (today: `shape.examine` only).
- Durable evidence patterns (ledger events, receipts, revision commits) are unchanged.
