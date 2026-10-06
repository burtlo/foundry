# Shape examination — judgment

## Purpose

Interpret the sealed intake **ticket** and prior clarifying Q&A (`prior_answers` in task input) with bounded project context. Identify ambiguity, missing constraints, and assumptions that would block a clear acceptance-criteria draft.

## Output (schema-bound only)

Return a single structured examination result — do not call CLI and do not choose the next workflow node.

- `draft_acceptance_criteria` — best current AC draft (list of strings).
- `assumptions` — explicit assumptions you are making.
- `questions` — open clarifying questions (empty when none); each needs `id`, `text`, `why_needed`.
- `decisions` — material judgments with `text` and `basis`.
- `summary` — short narrative of this examination round.

Ask clarifying questions only when answers would materially change scope or AC. Incorporate prior answers when `prior_answers` includes them.

The host records state from your result, manages the clarifying-question loop, and completes the visit when ready.
