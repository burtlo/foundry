---
name: review-archive-run
description: >-
  Evaluates a Foundry run (artifacts-first, optional transcript), presents the
  review, then archives into foundry/runs with a sequential slug. Use to capture
  notes and move a run out of the application workspace — including in-progress
  runs still on shape.examine or other waits.
---

# Review and archive run

Role: evaluation lead — review the run, show results, then archive into the Foundry `runs/` store.

Follow [steward UX](../rules/steward-ux.mdc): plain-language intent before CLI; use `foundry-invoke` fences.

Reference: [.cursor/skills/foundry-run-evaluation/SKILL.md](../skills/foundry-run-evaluation/SKILL.md).

## User input

| Field | Source |
|---|---|
| `run_path` | Typically `workspace/.foundry/runs/{run_id}` |
| `transcript_path` | Optional steward `.jsonl` (copied into archive if provided) |
| `prior_review_path` | Optional prior review |
| `focus` | Optional emphasis |
| `evaluation_id` | Default `review-1` |

## Procedure

### 1. Validate inputs

Confirm `run_path/snapshot.json` exists. If archiving an in-progress run, note `status: running`, active `wait`, and `.run.lock` in the evaluation — archiving is allowed but the run may still be resumable from a copy under `runs/`.

Bootstrap CLI from the application workspace:

```foundry-invoke
cli resolve
```

### 2. Evaluate

Launch **run-evaluator** with `run_path`, optional `transcript_path`, `prior_review_path`, `focus`, and `evaluation_id`.

Return full `summary_markdown` to the user **before** archiving.

### 3. Write review artifact

Write evaluator `summary_markdown` to:

`{run_path}/receipts/evaluation-{evaluation_id}.md`

Use an absolute path for the archive step.

### 4. Archive

Archive allocates the next slug under `{foundry_repo}/runs/` (e.g. `foundry-0002` when `foundry-0001` exists), independent of engine `run_id`.

```foundry-invoke
run archive --run "{run_id}" --review-file "{review_file_path}" --json
```

Add `--transcript "{transcript_path}"` when an external steward chat export exists.

Use `--run-dir` instead of `--run` when `run_path` is not under the default workspace layout.

On success, report:

- **Archive slug** and path (`archive_slug`, `archive_path`)
- **Original run id** in `archive/manifest.json`
- **Verdict**, `recommended_next_action`, and top findings

### 5. Dry-run only

```foundry-invoke
run archive --run "{run_id}" --dry-run --json
```

## Evaluator launch prompt

Same as [/evaluate-run](evaluate-run.md) evaluator block (`transcript_path` optional).

## Out of scope

| Action | Use when |
|---|---|
| `/evaluate-run` | Review only — no archive |
| `foundry shape` (new run) | New shape run |
| `/craft-execute` | Continue implementation after shape complete |

## What the user receives

1. Evaluation scorecard and findings in chat
2. Run tree under `runs/{archive_slug}/` (snapshot, ledger, artifacts, receipts)
3. `archive/manifest.json` (provenance, visits summary, git heads)
4. `archive/review.md` from step 3
5. `archive/transcript.jsonl` only if `--transcript` was passed
