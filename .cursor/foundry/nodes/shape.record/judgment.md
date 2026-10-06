# Shape record — judgment

## Purpose

Given `presented_ac` and the sealed presentation content, propose frozen `approved_ac` and living `plan_markdown` for publication — or BLOCKED when required inputs are missing or AC is too vague to freeze.

On reshape re-entry (`approved_ac` in task input), align the plan with prior approved criteria when refining after `shape.record.gate` hold.

## Output (schema-bound only)

Return a single structured record result — do not call CLI and do not choose the next workflow node.

- `plan_markdown` — full body for `plan.md` (scope, approach, acceptance criteria).
- `approved_ac` — frozen acceptance criteria text for run state.
- `verdict` — `PROCEED` when ready to publish; `BLOCKED` when not.
- `blockers` — required non-empty when `verdict` is `BLOCKED`.
- `summary` — short verdict line (one or two sentences).

When `presented_ac` or presentation content is missing, use `verdict: BLOCKED` with clear `blockers`.

The host patches record state, publishes the plan artifact, mirrors `workspace:plan.md`, seals the agent receipt, and completes the visit when you return `PROCEED`.
