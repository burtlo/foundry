# Shape examination - judgment

## Purpose

Understand the user's work request in light of the sealed intake **ticket** (`reads.state.ticket` / artifact from shape.intake). `normalized_translation` may be null until examination fills it.

## Conduct examination

- Identify ambiguity, missing constraints, and assumptions that would block a clear acceptance-criteria draft.
- Ask clarifying questions when answers materially change scope or AC (return them in `questions`).
- Incorporate prior question/answer history from `prior_answers` when present.
- Produce an updated `draft_acceptance_criteria` list, `assumptions`, and `decisions` reflecting the current understanding.

## Completion signal

Return a structured result only — do not choose the next node.

- `draft_acceptance_criteria` — best current AC draft.
- `questions` — open clarifying questions (empty when none).
- `summary` — short narrative of the examination.

The host records state, seals the agent receipt, and routes:

- Zero open questions — fast lane to presentation.
- Nonzero open questions — user gate for continue vs present with assumptions.

## Receipt content

Summarize the examination in `summary`. Routing and receipt sealing are host-owned after your result is accepted.
