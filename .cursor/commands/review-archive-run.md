---
name: review-archive-run
description: >-
  Evaluates a Foundry steward run from its chat transcript and run artifacts,
  presents the review to the user, then archives the run into foundry/runs with
  a sequential archive slug. Use after shape or execute to review, capture notes,
  and move the run out of the application workspace.
---

# Review and archive run

Role: evaluation lead — review the run, show results, then archive into the Foundry `runs/` store.

Follow [steward UX](../rules/steward-ux.mdc): lead each turn with a plain-language intent sentence; use `foundry-invoke` fences for Foundry CLI.

## User input

Capture from the user message (or `@` mentions):

| Field | Source |
|---|---|
| `run_path` | Run directory — typically `workspace/.foundry/runs/{run_id}` |
| `transcript_path` | Steward chat transcript (`.jsonl`) |
| `prior_review_path` | Optional prior review for regression comparison |
| `focus` | Optional emphasis areas |
| `evaluation_id` | Optional label (default `review-1`) |

## Procedure

### 1. Validate inputs

Confirm `run_path/snapshot.json` exists and `transcript_path` is readable.

```foundry-invoke
cli resolve --json
```

### 2. Evaluate

Launch the **run-evaluator** subagent with `run_path`, `transcript_path`, `prior_review_path`, `focus`, and `evaluation_id`.

Return the evaluator's full `summary_markdown` to the user in chat before archiving.

### 3. Write review artifact

Write the evaluator's `summary_markdown` to a temp file:

`{run_path}/receipts/evaluation-{evaluation_id}.md`

### 4. Archive

Archive assigns the next sequential slug under `{foundry_repo}/runs/` (e.g. `porcelain-0002` when `porcelain-0001` already exists), even when the engine `run_id` is still `porcelain-0001`.

```foundry-invoke
run archive --run "{run_id}" --transcript "{transcript_path}" --review-file "{review_file_path}" --json
```

`{review_file_path}` is the absolute path to the evaluation markdown written in step 3. Use `--run-dir` instead of `--run` when `run_path` is not under the default workspace layout.

On success, tell the user:

- **Archive slug** and path (`archive_slug`, `archive_path` from response)
- **Original run id** preserved in `archive/manifest.json`
- **Verdict** and top findings from the evaluation

### 5. Dry-run only

When the user asks to preview without moving:

```foundry-invoke
run archive --run "{run_id}" --dry-run --json
```

## Evaluator launch prompt

```
Evaluate the Foundry run per your agent instructions.

## Inputs

| Field | Value |
|---|---|
| run_path | {run_path} |
| transcript_path | {transcript_path} |
| prior_review_path | {prior_review_path or "none"} |
| focus | {focus or "full evaluation"} |
| evaluation_id | {evaluation_id or "review-1"} |

## Task

Follow run-evaluator instructions exactly. Return full JSON including summary_markdown.
```

## Out of scope

| Action | Use when |
|---|---|
| `/evaluate-run` | Review only — no archive |
| `foundry shape` (new run) | Starting a new shape run |
| `/craft-execute` | Continuing to implementation |

## What the user receives

1. Full evaluation scorecard and findings in chat
2. Run moved to `foundry/runs/{archive_slug}/`
3. `archive/manifest.json` with provenance (commits, visits, original `run_id`)
4. `archive/review.md` and `archive/transcript.jsonl` copies
