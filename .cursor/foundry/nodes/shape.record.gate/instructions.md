# Record acceptance criteria gate

## Goal

Record the user's confirmation that the living plan and approved acceptance criteria are understood before execute may start.

## While opened

This gate is a **two-turn minimum** — presentation turn, then decision turn.

### Turn 1 — Presentation (end turn here)

Send **one user-facing message** with sections **in this order**:

1. **Header** — `## Record acceptance criteria — {run_id}` (include node title from context).
2. **Living plan** — read and render the **full** plan markdown from `reads.state.plan_path`, the `shape.record.plan` artifact in `reads.artifacts`, or `workspace:plan.md` when present in context. Do not summarize.
3. **Approved acceptance criteria** — copy `reads.state.approved_ac` **verbatim** as a numbered list. Do not paraphrase or shorten.
4. **STOP line** — end with:

```markdown
---
**Review the living plan and approved acceptance criteria above.** Reply on your next message with one of:
- **confirm** — shared understanding; proceed to execute
- **hold** — pause; you need changes before execute may start

Do not decide until you reply on your next message.
```

**End the agent turn here.** Do not call `gate decide`, **AskQuestion**, or other advancing tools in this turn.

### Turn 2 — Decision

On the **next** user message:

- If the user asked to see the plan or AC first, or plan / `approved_ac` was skipped or summarized → **re-run Turn 1** and **STOP** again.
- Map **confirm** (or equivalent approval) to decision `record`. If the user holds or requests changes, clarify in chat; do not call `gate decide` until they confirm.
- Optionally use **AskQuestion** or plain chat to confirm, then record the decision:

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision record --json
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
