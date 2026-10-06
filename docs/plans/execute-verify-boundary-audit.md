# Execute / Verify boundary audit

Host advancement behavior for nodes from `execute.start` through `deliver.stub` as of remediation step 4. Full step executors and engine-gate routing belong to workflow-02.

## Summary

| Status | Meaning |
| --- | --- |
| **gate-user** | User decision wait (`gate:{node_id}`) or `foundry start` at `execute.start` |
| **gate-engine** | Machine gate; checks declared in flow; host does not auto-complete routing yet |
| **unsupported** | Operator wait: node not implemented; `request_ref` is `unsupported:{node_id}` |
| **implemented** | Host-owned executor or `tasks/{node_id}.yaml` agent binding |

All **step** nodes in Execute, Verify, and Deliver are **unsupported** until workflow-02. Shape steps (`shape.intake`, `shape.examine`, `shape.present`, `shape.record`) remain host-implemented or agent-bound as before.

## Per-node status

| Node | Status | Advance behavior |
| --- | --- | --- |
| `execute.start` | gate-user | Decision wait; `foundry start` records authorization and accepts gate |
| `execute.intake` | unsupported | Operator wait `unsupported:execute.intake` |
| `execute.intake.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `execute.branch` | unsupported | Operator wait `unsupported:execute.branch` |
| `execute.plan` | unsupported | Operator wait `unsupported:execute.plan` |
| `execute.build` | unsupported | Operator wait `unsupported:execute.build` |
| `execute.test` | unsupported | Operator wait `unsupported:execute.test` |
| `execute.test.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `execute.repair.limit.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `execute.commit` | unsupported | Operator wait `unsupported:execute.commit` |
| `execute.commit.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `verify.intake` | unsupported | Operator wait `unsupported:verify.intake` |
| `verify.intake.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `verify.acceptance` | unsupported | Operator wait `unsupported:verify.acceptance` |
| `verify.acceptance.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `verify.code_quality` | unsupported | Operator wait `unsupported:verify.code_quality` |
| `verify.code_quality.gate` | gate-engine | Engine gate (checks only; no host auto-route yet) |
| `verify.code_review` | unsupported | Operator wait `unsupported:verify.code_review` |
| `verify.code_review.gate` | gate-user | Decision wait; user `gate decide` / `decide` |
| `verify.complete` | unsupported | Operator wait `unsupported:verify.complete` |
| `verify.complete.gate` | gate-user | Decision wait; user `gate decide` / `decide` |
| `deliver.stub` | unsupported | Operator wait `unsupported:deliver.stub` |

## Preserved contracts

- `execute.start` remains a user gate with explicit `foundry start` authorization (`execute.authorization.recorded`).
- Decision and `user_input` waits are unchanged for Shape and user gates.
- Agent waits remain where `tasks/{node_id}.yaml` exists (today: `shape.examine` only).
- Durable evidence patterns (ledger events, receipts, revision commits) are unchanged.
