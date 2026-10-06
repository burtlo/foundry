# Execute test gate

## Goal

Let the engine map sealed **execute.test** agent receipt command exit codes to **pass** or **repair**, then advance into commit or the repair loop. This gate has no user decision and no worker.

## While opened

The host normally resolves this gate on **`run advance`**. When you are driving the run manually:

```foundry-invoke
run advance --run "{run_id}" --json
```

Repeat until the active node is **`execute.commit`** (pass) or **`execute.repair.limit.gate`** (repair), or the host reports no further progress.

### If advance does not pass the gate

- Do **not** call `gate decide` — the engine owns this gate (`decider: engine`).
- Inspect **`reads.test_receipt`** in the steward context (and the sealed **execute.test** visit). Non-zero `commands[]` exit codes imply **repair**; all zeros imply **pass**.
- Do not call `visit transition` or patch run state on this node.

## Boundaries

- Do not call `gate decide`.
- Do not launch a worker — this gate has no worker binding.
- Do not publish artifacts or seal receipts — evidence comes from the prior **execute.test** visit.
- Do not name routing targets — the engine selects the connection after decision **pass** or **repair**.
