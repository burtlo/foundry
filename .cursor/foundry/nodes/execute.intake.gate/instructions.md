# Execute intake gate

## Goal

Let the engine confirm the sealed **execute.intake** receipt is **passed**, then advance into branch creation. This gate has no user decision and no worker.

## While opened

The host normally resolves this gate on **`run advance`**. When you are driving the run manually:

```foundry-invoke
run advance --run "{run_id}" --json
```

Repeat until the active node is **`execute.branch`** (or the host reports no further progress).

### If advance does not pass the gate

- Do **not** call `gate decide` — the engine owns this gate (`decider: engine`).
- Inspect **`reads.intake_receipt`** in the steward context (and the sealed **execute.intake** visit). Status **`blocked`** or **`failed`** means validation failed upstream; remediate on **execute.intake** (clean git, frozen plan/AC alignment) and re-run intake completion before expecting this gate to pass.
- Do not call `visit transition` or patch run state on this node.

## Boundaries

- Do not call `gate decide`.
- Do not launch a worker — this gate has no worker binding.
- Do not publish artifacts or seal receipts — evidence comes from the prior **execute.intake** visit.
- Do not name routing targets — the engine selects the connection after decision **pass**.
