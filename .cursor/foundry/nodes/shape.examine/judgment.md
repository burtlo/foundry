# Shape examination - judgment

## Purpose

Understand the user's work request in light of the sealed intake **ticket** (`reads.state.ticket` / artifact from shape.intake). `normalized_translation` may be null until examination fills it.

## Conduct examination

- Identify ambiguity, missing constraints, and assumptions that would block a clear acceptance-criteria draft.
- Ask clarifying questions via `allow.user.ask` when answers materially change scope or AC.
- Record questions in `clarifying_questions` (structured items with `status`); the engine derives `open_clarifying_questions_count` for routing when that list is present.
- Incorporate user answers into `draft_ac` and supporting state (`assumptions`, `examination_decisions`, counters).

## Completion signal

Before the operations sequence seals and transitions:

- Set `draft_ac` to the best current acceptance-criteria draft.
- Ensure routing state reflects unresolved questions (structured list and/or `open_clarifying_questions_count`).
  - Zero open questions — engine routes to shape.present (fast lane).
  - Nonzero — engine routes to shape.examine.gate for user decision.

Do not choose the next node; routing is engine policy from state.

## Receipt content

Summarize the examination conversation in the agent receipt. Use `agent.name` **shape.steward** (this visit has no worker).
