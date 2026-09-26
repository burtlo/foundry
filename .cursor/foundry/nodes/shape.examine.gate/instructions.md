# Examination gate

## Goal

Record the user's decision whether to present the plan or continue questioning.

## While opened

Review `produces.options` and `## Gate prompt` in the context packet. Present the choice to the user, then record their decision:

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision present --json
```

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision continue --json
```

Use exactly one decision value from `produces.options`. The engine seals this visit and admits the next node.

## Boundaries

- Do not call `visit transition` — gates close only via `gate decide`.
- Do not name or choose routing targets — the engine selects the connection from your decision.
- Do not launch a worker — this gate has no worker binding.
- Do not publish artifacts or seal receipts — gates produce a decision only.
- Do not patch run state — no state paths are allowed on this gate.
