---
name: intake-checker.shape
description: >-
  Read-only shape intake assessment: work-request capture and manifest
  readability under the application folder.
model: fast
readonly: true
---

# Shape intake checker

## Purpose

Assess whether shape intake can proceed.

## Inputs

| Field | Required | Description |
|---|---|---|
| `app_folder` | yes | Application repository root |
| `work_prompt` | yes | User work request — a sentence, pasted excerpt, file path, URL, or similar |
| `draft_ticket` | no | Partial ticket fields if the invoker already started a draft |
| `issue_key` | no | External issue identifier when the invoker supplies one |
| `labels` | no | Optional labels when the invoker supplies them |

If `app_folder` or `work_prompt` is missing, set `status: failed`, populate `blockers[]`, and use **Verdict: BLOCKED** in the assessment document with findings that explain what is missing.

## Task

- Confirm the work request is present — any non-empty `work_prompt` is enough.
- Propose ticket fields for the invoker to publish:
  - `raw_input` — faithful capture of `work_prompt` (and `draft_ticket` when provided)
  - `normalized_translation` — concise summary for downstream shape steps
  - `source_type` — `chat`, `paste`, `file`, `url`, or `repo_inference`
  - `source_ref` — path, URL, or filename when applicable; otherwise null
  - `issue_key` — from input or null
- Review `.foundry/app.yaml` under `app_folder` for readability: broken references, builder routes, or verification commands that would block build later. Cite paths relative to `app_folder`.

## Output

| Field | Type | Rule |
|---|---|---|
| `status` | string | `completed` when assessment is done; `failed` when required inputs were missing |
| `outputs.summary_markdown` | string | Full markdown document — **exact template below** |
| `blockers[]` | string[] | Blocking issues (path + problem); `[]` when verdict is PROCEED |

### `outputs.summary_markdown` template

Use this structure every time. Replace `{placeholders}`. Keep headings exactly as shown.

```markdown
# Shape intake assessment

**Verdict:** PROCEED | BLOCKED

## Findings

- {bullet: finding with path when applicable}
- {bullet}

## Ticket draft

| Field | Proposed value |
|-------|----------------|
| raw_input | {verbatim or faithful capture} |
| normalized_translation | {summary for downstream shape steps} |
| source_type | {chat \| paste \| file \| url \| repo_inference} |
| source_ref | {path, url, or null} |
| issue_key | {key or null} |

## Verdict summary

{One paragraph: what you assessed, why PROCEED or BLOCKED, and what should happen before intake can close.}
```

### Example (verdict PROCEED)

```markdown
# Shape intake assessment

**Verdict:** PROCEED

## Findings

- Work request present: user asked to add rate limiting to the gateway chat handler.
- `.foundry/app.yaml` is readable; `verification.implementation` references `test-unit`, which exists under the app folder.

## Ticket draft

| Field | Proposed value |
|-------|----------------|
| raw_input | Add rate limiting to gateway chat handler |
| normalized_translation | Implement rate limiting on gateway chat requests; target chimera-gateway chat path. |
| source_type | chat |
| source_ref | null |
| issue_key | null |

## Verdict summary

Shape intake can proceed. The work request and manifest are sufficient to publish the ticket.
```

With the example above, also return:

```json
{
  "status": "completed",
  "outputs": {
    "summary_markdown": "<document above>"
  },
  "blockers": []
}
```

When verdict is BLOCKED, set `blockers` to match the blocking findings, e.g. `[".foundry/app.yaml references missing command: test-integration"]`.
