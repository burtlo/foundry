# Verify complete gate

## Goal

Record the user's acceptance that the implementation is complete and the verify phase may end.

## While opened

This gate is a **two-turn minimum** — presentation turn, then decision turn.

### Turn 1 — Presentation (end turn here)

Send **one user-facing message** with sections **in this order**:

1. **Header** — `## Verify complete — {run_id}` (include node title from context).
2. **Summary** — brief confirmation that code review passed and the implementation is ready to deliver.
3. **STOP line** — end with:

```markdown
---
**Accept the implementation to end the verify phase.** Reply on your next message with:
- **accept** — proceed to deliver

Do not decide until you reply on your next message.
```

**End the agent turn here.** Do not call `gate decide`, **AskQuestion**, or other advancing tools in this turn.

### Turn 2 — Decision

On the **next** user message:

- If the user asked for more context first → **re-run Turn 1** and **STOP** again.
- Otherwise interpret **accept**, optionally use **AskQuestion** or plain chat to confirm, then record the decision:

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision accept --json
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
