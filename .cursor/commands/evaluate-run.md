---
name: evaluate-run
description: >-
  Evaluates a Foundry steward run from its chat transcript and run artifacts.
  Checks task correctness, node instruction compliance, operator UX, communication
  quality, and shape deliverables (plan, presentation, AC). Use after a shape or
  execute run to review steward behavior and output quality.
---

# Evaluate run

Role: evaluation lead — launch the run evaluator and return a structured review.

## User input

Capture from the user message:

| Field | Source |
|---|---|
| `run_path` | Run directory (`.foundry/runs/{run_id}` or archived `foundry/runs/{run_id}`) |
| `transcript_path` | Steward chat transcript (`.jsonl`) |
| `prior_review_path` | Optional prior review markdown or archive `review.md` |
| `focus` | Optional emphasis areas |
| `evaluation_id` | Optional label (`review-1`, `review-2`, …) |

If the user `@`-mentions a run folder and transcript, use those paths directly.

## Procedure

1. Confirm `run_path` contains `snapshot.json` and `transcript_path` exists.
2. Launch the **run-evaluator** subagent with all inputs.
3. Return the evaluator's `summary_markdown` to the user in chat.
4. If `verdict` is `fail` or major findings exist, list top recommendations.

## Evaluator launch prompt

Pass this structure to the subagent:

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

Follow run-evaluator instructions exactly. Investigate snapshot, transcript, artifacts, node instructions, and deliverables. Return full JSON output including summary_markdown.
```

For a **second opinion**, re-launch with a new `evaluation_id` and include the first evaluation's `summary_markdown` or path as `prior_review_path`.

## Out of scope

| Action | Use when |
|---|---|
| Archiving the run after review | `/review-archive-run` |
| Modifying the run or re-running shape | User wants a redo, not a review |
| `foundry shape` (new run) | Starting a new shape run |
| `/craft-execute` | Continuing to implementation |
| Fixing Foundry instructions | Separate implementation task after review |

## What good output looks like

- Scorecard across five dimensions with evidence
- Per-visit instruction compliance matrix
- Gate presentation/decision turn analysis
- Plan and presentation quality notes
- Clear verdict on whether the run is safe to continue
