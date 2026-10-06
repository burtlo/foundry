# Start execute phase

## Goal

Present the frozen living plan and approved acceptance criteria, then record explicit user authorization to begin Execute via `foundry start`.

## While opened

This gate is a **two-turn minimum** — presentation turn, then authorization turn.

### Turn 1 — Presentation (end turn here)

Send **one user-facing message** with sections **in this order**:

1. **Header** — use exactly `## Authorize execute — {run_id}` as an H2 markdown heading.
2. **Living plan** — render the **full** plan markdown from the steward context section **`## Living plan`** (resolved `shape.record.plan` in `reads.artifacts`). Do not summarize or read undeclared paths.
3. **Approved acceptance criteria** — copy `reads.state.approved_ac` **verbatim**, preserving its markdown format. Do not paraphrase or reformat.
4. **Authorization** — state that Shape is complete and Execute may begin only after the user runs `foundry start` for this run (on their feature branch when working in git). The steward may invoke `start` on Turn 2 after explicit confirmation.
5. **STOP line** — end with:

```markdown
---
**Review the living plan and approved acceptance criteria above.** Reply on your next message when you are ready to authorize Execute (or say you have already run `foundry start` on your branch).

Do not call `start` until you reply on your next message.
```

**End the agent turn here.** Do not call `start`, **AskQuestion**, or other advancing tools in this turn.

### Turn 2 — Authorization

On the **next** user message:

- If the user asked to see the plan or AC first, or content was skipped or summarized → **re-run Turn 1** and **STOP** again.
- When the user explicitly authorizes Execute (or confirms they ran `foundry start` locally and you should reconcile), record authorization:

```foundry-invoke
start --run "{run_id}" --json
```

Add `--no-host` and `--local` when acceptance or the user's environment requires disk-side authorization without the job host.

The engine records `execute.authorization.recorded`, accepts this gate, and admits `execute.intake`.

## Boundaries

- Do not call `gate decide` — this gate closes only via `start` (operator authorization).
- Do not call `visit transition`.
- Do not use **AskQuestion** in the presentation turn (Turn 1).
- Do not call `start` in the presentation turn (Turn 1).
- Do not name or choose routing targets — the engine selects the connection after authorization.
- Do not launch a worker — this gate has no worker binding.
- Do not publish artifacts or seal receipts — authorization and routing only.
- Do not patch run state — no state paths are allowed on this gate.
