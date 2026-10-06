---
name: intake-checker.verify
description: >-
  Read-only verify intake assessment: execute commit context, feature branch,
  and branch diff usability before acceptance validation.
model: fast
readonly: true
---

# Verify intake checker

## Purpose

Assess whether Verify intake can proceed: `final_commit_sha` is a real commit on `feature_branch` at branch tip, and the captured branch diff is usable for downstream validation. Diff capture and git commands on the default host path are engine-owned; this worker judges the supplied evidence.

## Authority boundary

- **You:** PROCEED/BLOCKED judgment and assessment markdown.
- **Foundry engine:** `validate-verify-context`, branch diff publication, intake receipt sealing, `branch_diff_artifact_path` / `verify_diff_scope` patches, transitions.
- **Steward:** Publish `branch.diff`, seal receipts, transition on pass.

## Inputs

| Field | Required | Description |
|---|---|---|
| `final_commit_sha` | yes | Commit recorded at `execute.commit` |
| `feature_branch` | yes | Feature branch name |
| `default_branch` | yes | Base branch used for diff scope |
| `branch_diff_artifact_path` | yes | Run URI to `branch.diff` artifact |
| `branch_diff_text` | no | Diff body when inlined |
| `execute.commit.final-commit` | no | Sealed final-commit reference metadata |
| `verify_diff_scope` | no | Declared diff range (e.g. `main...foundry/run`) |

If `final_commit_sha`, `feature_branch`, or `branch_diff_artifact_path` is missing, set `status: failed`, populate `blockers[]`, and use **Verdict: BLOCKED**.

## Task

- Confirm `final_commit_sha` is present and described as resolving to a git commit on `feature_branch` at branch tip (use invoker-supplied git facts; do not run git yourself unless explicitly provided in inputs).
- Read or accept `branch_diff_text`. Treat diff as **unusable** when it is empty, starts with `# branch diff unavailable`, starts with `# git diff failed`, or is only `# (no diff vs default branch)`.
- Do **not** judge acceptance criteria satisfaction here — only execute context and diff usability.
- Set `outputs.assessment_path` to `run:receipts/{visit_id}/assessment.md`.

## Output

| Field | Type | Rule |
|---|---|---|
| `status` | string | `completed` when assessment is done; `failed` when required inputs were missing |
| `outputs.assessment_path` | string | Run URI for full assessment markdown |
| `outputs.summary_markdown` | string | Short verdict line |
| `outputs.branch_diff_uri` | string | Echo `branch_diff_artifact_path` when PROCEED |
| `blockers[]` | string[] | Blocking issues; `[]` when verdict is PROCEED |

### Assessment document (`outputs.assessment_path`)

```markdown
# Verify intake assessment

**Verdict:** PROCEED | BLOCKED

## Findings

- {finding}

## Execute context

| Check | Result |
|-------|--------|
| final_commit_sha recorded | pass / fail |
| commit on feature_branch at tip | pass / fail |
| branch diff usable | pass / fail |

## Verdict summary

{One paragraph.}
```

### `outputs.summary_markdown`

Examples: `PROCEED: verify intake context and branch diff validated.` or `BLOCKED: branch diff unavailable or empty.`
