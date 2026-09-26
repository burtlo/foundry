# Code review gate

## Goal

Record the user's decision whether to accept the verified implementation, reject for repairs, or reshape when acceptance criteria are wrong.

## While opened

This gate is a **two-turn minimum** — presentation turn, then decision turn.

### Turn 1 — Presentation (end turn here)

Send **one user-facing message** with sections **in this order**:

1. **Header** — `## Code review — {run_id}` (include node title from context).
2. **Review summary** — summarize verify findings, branch diff scope, and any open issues from `reads.state` and `reads.artifacts`.
3. **STOP line** — end with:

```markdown
---
**Review the implementation above.** Reply on your next message with one of:
- **accept** — approve verified implementation
- **reject** — request repairs (standards or implementation fixes)
- **reshape** — acceptance criteria are wrong; return to shape intake

Do not decide until you reply on your next message.
```

**End the agent turn here.** Do not call `gate decide`, **AskQuestion**, or other advancing tools in this turn.

### Turn 2 — Decision

On the **next** user message:

- If review context was skipped or summarized → **re-run Turn 1** and **STOP** again.
- Otherwise interpret the reply (`accept`, `reject`, or `reshape`), optionally use **AskQuestion** or plain chat to confirm, then record exactly one decision:

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision accept --json
```

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision reject --json
```

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision reshape --json
```

Use exactly one decision value from `produces.options`. The engine seals this visit and admits the next node.

## Boundaries

- Do not call `visit transition` — gates close only via `gate decide`.
- Do not use **AskQuestion** in the presentation turn (Turn 1).
- Do not call `gate decide` in the presentation turn (Turn 1).
- Do not name or choose routing targets — the engine selects the connection from your decision.
- Do not launch a worker — this gate has no worker binding.
- Do not publish artifacts or seal receipts — gates produce a decision only.
- Do not patch run state — no state paths are allowed on this gate.
