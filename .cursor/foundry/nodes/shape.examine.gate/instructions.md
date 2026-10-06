# Examination gate

## Goal

Record the user's decision whether to reject and continue examination, or accept and proceed to shape presentation (plan not shown yet).

## While opened

This gate is a **two-turn minimum** — presentation turn, then decision turn.

### Turn 1 — Presentation (end turn here)

Send **one user-facing message** with sections **in this order**:

1. **Header** — `## Examination gate — {run_id}` (include node title from context).
2. **Open clarifying questions** — from `reads.state.clarifying_questions`; distinguish open vs answered when the structure supports it. Include `reads.state.open_clarifying_questions_count` when useful.
3. **Assumptions** — from `reads.state.assumptions`.
4. **Draft acceptance criteria** — copy `reads.state.draft_ac` **verbatim**, preserving its markdown format. Do not paraphrase or shorten.
5. **STOP line** — end with:

```markdown
---
**Review the open questions, assumptions, and draft AC above.** Reply on your next message with one of:
- **reject** — continue examination and questioning
- **accept** — proceed to present the plan (with remaining assumptions visible)

Do not decide until you reply on your next message.
```

**End the agent turn here.** Do not call `gate decide`, **AskQuestion**, or other advancing tools in this turn.

### Turn 2 — Decision

On the **next** user message:

- If the user asked to see questions, assumptions, or draft AC first, or any section was skipped or summarized -> **re-run Turn 1** and **STOP** again.
- Otherwise interpret the reply (`reject` or `accept`), optionally use **AskQuestion** or plain chat to confirm, then record exactly one decision:

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision reject
```

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision accept
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
