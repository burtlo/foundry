# Verify complete gate

## Goal

Record user acceptance to end the verify phase and proceed to deliver.

## While opened

**Two-turn minimum** — presentation turn, then decision turn.

### Turn 1 — Presentation (end turn here)

Send **one user-facing message** with sections **in this order**:

1. **Header** — `## Verify complete — {run_id}` (include node title from context).
2. **Handoff** — from steward context **`## Reads` → `### State`**: present `verified_at`, `feature_branch`, and `final_commit_sha` exactly as shown. Do not reload verify notes, branch diff, or other artifacts — code review accept is already recorded.
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

- If the user asked to see handoff fields first, or any were skipped or summarized → **re-run Turn 1** and **STOP** again.
- Otherwise interpret **accept**, optionally use **AskQuestion** or plain chat to confirm, then record the decision:

```foundry-invoke
gate decide --run "{run_id}" --visit "{visit_id}" --decision accept --json
```

Use exactly one value from `produces.options`. The engine seals this visit and admits the next node.

## Boundaries

- Gates close only via `gate decide` — not `visit transition`.
- No **AskQuestion** or `gate decide` on Turn 1.
- No routing targets, workers, artifacts, receipts, or run state patches on this gate.
