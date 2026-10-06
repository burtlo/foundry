# Shape presentation — judgment

## Purpose

Given examination state (ticket, `draft_ac`, assumptions, decisions, clarifying Q&A), produce succinct user-facing presentation markdown and `presented_ac` for the plan gate — or BLOCKED when required inputs are missing or AC is too vague to present.

On reshape re-entry (`approved_ac` in task input), align the presentation with the approved criteria context when present.

## Output (schema-bound only)

Return a single structured presentation result — do not call CLI and do not choose the next workflow node.

- `presentation_markdown` — full body for `presentation.md` (scope, approach, acceptance criteria).
- `presented_ac` — acceptance criteria text shown to the user (usually aligned with `draft_ac`).
- `verdict` — `PROCEED` when ready to publish; `BLOCKED` when not.
- `blockers` — required non-empty when `verdict` is `BLOCKED`.
- `summary` — short verdict line (one or two sentences).

When `ticket` or `draft_ac` is missing, use `verdict: BLOCKED` with clear `blockers`.

The host publishes the artifact, seals the agent receipt, and completes the visit when you return `PROCEED`.
