# Record acceptance criteria gate

## Goal

Record the user's confirmation that the living plan and approved acceptance criteria are understood before execute may start.

## While opened

This gate is a **two-turn minimum** — presentation turn, then decision turn.

### Turn 1 — Presentation (end turn here)

Send **one user-facing message** with sections **in this order**:

1. **Header** — use exactly `## Record acceptance criteria — {run_id}` as an H2 markdown heading (not bold alone, not H1, not a shortened title). Do not open with post-record narration (e.g. "Recorded your decision" or "AC are frozen") — the user has not confirmed at this gate yet.
2. **Living plan** — render the **full** plan markdown from the steward context section **`## Living plan`** (resolved `shape.record.plan` in `reads.artifacts`). Do not summarize or read undeclared paths.
3. **Approved acceptance criteria** — copy `reads.state.approved_ac` **verbatim**, preserving its markdown format (numbered list, checkbox list, or plain lines). Do not paraphrase, shorten, or convert between formats (e.g. do not turn numbered items into `- [ ]` checkboxes).
4. **STOP line** — end with:

```markdown
---
**Review the living plan and approved acceptance criteria above.** Reply on your next message with one of:
- **accept** — shared understanding; proceed to execute
- **hold** — pause; you need changes before execute may start

Do not decide until you reply on your next message.
```

**End the agent turn here.** Do not call `gate decide`, **AskQuestion**, or other advancing tools in this turn.

### Turn 2 — Decision

On the **next** user message:

- If the user asked to see the plan or AC first, or plan / `approved_ac` was skipped or summarized -> **re-run Turn 1** and **STOP** again.
- If the user holds or requests changes, clarify in chat; do not call `gate decide` until they accept.
- Map **accept** (or equivalent approval) to decision `accept`. Optionally use **AskQuestion** or plain chat to confirm, then record exactly one decision:

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision accept --json
```

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision hold --json
```

Use exactly one decision value from `produces.options`. The engine seals this visit and admits the next node.

## Boundaries

- Do not call `visit transition` — gates close only via `gate decide`.
- Do not use **AskQuestion** in the presentation turn (Turn 1).
- Do not call `gate decide` in the presentation turn (Turn 1).
- Do not call `gate decide` when the user holds — clarify until they accept.
- Do not name or choose routing targets — the engine selects the connection from your decision.
- Do not launch a worker — this gate has no worker binding.
- Do not publish artifacts or seal receipts — gates produce a decision only.
- Do not patch run state — no state paths are allowed on this gate.
