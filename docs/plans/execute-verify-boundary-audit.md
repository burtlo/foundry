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
| **gate-engine** | Machine gate; `resolve_engine_gate` on advance where a resolver exists; host routes after decision |
| **implemented** | Host-owned step executor, git/mechanical advance, or agent task binding |
| **unsupported** | Operator wait (`unsupported:{node_id}`) — none expected on this path after workflow-02 skeleton |

## Per-node status

| Node | Status | Advance behavior |
| --- | --- | --- |
| `execute.start` | gate-user | Decision wait; `foundry start` records authorization and accepts gate |
| `execute.intake` | implemented | Host-owned step executor or task binding |
| `execute.intake.gate` | gate-engine | Engine gate; `resolve_engine_gate` on advance (host routes after decision) |
| `execute.branch` | implemented | Git/mechanical advance class (`run_execute_branch_complete`) |
| `execute.plan` | implemented | Agent task binding (`execute.plan`); `dispatch_task_bound_advance` after submit |
| `execute.build` | implemented | Host-owned step executor or task binding |
| `execute.test` | implemented | Host-owned step executor or task binding |
| `execute.test.gate` | gate-engine | Engine gate; `resolve_engine_gate` on advance (host routes after decision) |
| `execute.repair.limit.gate` | gate-engine | Engine gate; `resolve_engine_gate` on advance (host routes after decision) |
| `execute.commit` | implemented | Host-owned step executor or task binding |
| `execute.commit.gate` | gate-engine | Engine gate; `resolve_engine_gate` on advance (host routes after decision) |
| `verify.intake` | implemented | Host-owned step executor or task binding |
| `verify.intake.gate` | gate-engine | Engine gate; `resolve_engine_gate` on advance (host routes after decision) |
| `verify.acceptance` | implemented | Agent task binding (`verify.acceptance`); `dispatch_task_bound_advance` after submit |
| `verify.acceptance.gate` | gate-engine | Engine gate; `resolve_engine_gate` on advance (host routes after decision) |
| `verify.code_quality` | implemented | Host-owned step executor or task binding |
| `verify.code_quality.gate` | gate-engine | Engine gate; `resolve_engine_gate` on advance (host routes after decision) |
| `verify.code_review` | implemented | Host-owned step executor or task binding |
| `verify.code_review.gate` | gate-user | Decision wait; user `gate decide` / `decide` |
| `verify.complete` | implemented | Host-owned step executor or task binding |
| `verify.complete.gate` | gate-user | Decision wait; user `gate decide` / `decide` |
| `deliver.stub` | implemented | Host-owned step executor or task binding |

## Preserved contracts

- `execute.start` remains a user gate with explicit `foundry start` authorization (`execute.authorization.recorded`).
- Decision and `user_input` waits are unchanged for Shape and user gates.
- Agent waits remain where `tasks/{node_id}.yaml` exists (e.g. `execute.plan`, `verify.acceptance`, shape judgment tasks).
- Durable evidence patterns (ledger events, receipts, revision commits) are unchanged.
