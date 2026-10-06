# Plan presentation gate

## Goal

Record the user's decision whether to reject and refine the plan through further examination, or accept and proceed to record acceptance criteria.

## While opened

This gate is a **two-turn minimum** — presentation turn, then decision turn.

### Turn 1 — Presentation (end turn here)

Send **one user-facing message** with sections **in this order**:

1. **Header** — `## Plan presentation — {run_id}` (include node title from context).
2. **Presentation** — read and render the **full** presentation markdown from `reads.state.presentation_artifact_path` (or the `shape.present.presentation` artifact in `reads.artifacts`). Do not summarize.
3. **Presented acceptance criteria** — copy `reads.state.presented_ac` **verbatim**, preserving its markdown format (numbered list, checkbox list, or plain lines). Do not paraphrase, shorten, or convert between formats (e.g. do not turn numbered items into `- [ ]` checkboxes).
4. **STOP line** — end with:

```markdown
---
**Review the plan and acceptance criteria above.** Reply on your next message with one of:
- **reject** — return to examination with remaining questions
- **accept** — proceed to record acceptance criteria

Do not decide until you reply on your next message.
```

**End the agent turn here.** Do not call `gate decide`, **AskQuestion**, or other advancing tools in this turn.

### Turn 2 — Decision

On the **next** user message:

- If the user asked to see the plan or AC first, or presentation / `presented_ac` was skipped or summarized -> **re-run Turn 1** and **STOP** again.
- Otherwise interpret the reply (`reject` or `accept`), optionally use **AskQuestion** or plain chat to confirm, then record exactly one decision:

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision reject --json
```

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
