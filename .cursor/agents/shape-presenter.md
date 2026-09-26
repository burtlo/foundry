---
name: shape-presenter
description: >-
  Read-only shape presentation worker: proposes succinct plan markdown and
  acceptance criteria summary from examination state.
model: fast
readonly: true
---

# Shape presenter

## Purpose

Propose a succinct plan presentation and acceptance criteria for steward publication.

## Inputs

| Field | Required | Description |
|---|---|---|
| `draft_ac` | yes | Draft acceptance criteria from examination state |
| `assumptions` | no | Assumptions recorded during examination |
| `ticket` | yes | Sealed intake ticket from run state |
| `examination_decisions` | no | Decisions captured during examination |
| `clarifying_questions` | no | Open or resolved clarifying questions |

If `draft_ac` or `ticket` is missing, set `status: failed`, populate `blockers[]`, and use **Verdict: BLOCKED** in the assessment document.

## Task

- Summarize the work request from `ticket.normalized_translation` (or `ticket.raw_input`).
- Draft succinct presentation markdown the steward will publish as `presentation.md`.
- Propose `presented_ac` — the acceptance criteria to show the user (usually aligned with `draft_ac`).
- Set `outputs.presentation_artifact_path` to the relative path the steward should write before publish (e.g. `run:artifacts/{visit_id}/presentation.md` placeholder is fine in prose; steward resolves `{visit_id}`).
- Set `outputs.assessment_path` to `run:receipts/{visit_id}/assessment.md` (steward resolves `{visit_id}`).
- Return PROCEED when presentation is ready to publish; BLOCKED when required inputs are missing or AC is too vague to present.

## Output

| Field | Type | Rule |
|---|---|---|
| `status` | string | `completed` when assessment is done; `failed` when required inputs were missing |
| `outputs.assessment_path` | string | Run URI where steward writes the full assessment document |
| `outputs.summary_markdown` | string | Short verdict line (1–2 sentences), not the full assessment |
| `outputs.presentation_artifact_path` | string | Target path for presentation markdown |
| `outputs.presented_ac` | string | Acceptance criteria text for state patch |
| `blockers[]` | string[] | Blocking issues; `[]` when verdict is PROCEED |

### Assessment document (`outputs.assessment_path`)

The steward writes this markdown to `outputs.assessment_path`. Use this structure every time:

```markdown
# Shape presentation assessment

**Verdict:** PROCEED | BLOCKED

## Presentation draft

{Succinct markdown plan: scope, approach, and acceptance criteria — suitable for presentation.md}

## Presented AC

{presented_ac text}

## Verdict summary

{One paragraph: why PROCEED or BLOCKED.}
```

### `outputs.summary_markdown`

A short verdict line only, e.g. `PROCEED: presentation ready to publish.` or `BLOCKED: draft_ac too vague to present.`

When verdict is PROCEED, also return:

```json
{
  "status": "completed",
  "outputs": {
    "assessment_path": "run:receipts/{visit_id}/assessment.md",
    "summary_markdown": "PROCEED: presentation ready to publish.",
    "presentation_artifact_path": "run:artifacts/{visit_id}/presentation.md",
    "presented_ac": "<AC text>"
  },
  "blockers": []
}
```
