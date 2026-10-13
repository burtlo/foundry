---
name: evaluate-run
description: >-
  Evaluates a Foundry run from snapshot, ledger, artifacts, and optional steward
  chat transcript. Covers engine correctness, judgment quality, steward gates,
  operator waits, and phase-appropriate deliverables. Use after shape, execute,
  or verify — including in-progress runs parked on agent or user_input waits.
---

# Evaluate run

Role: evaluation lead — launch **run-evaluator** and return a structured review.

Domain reference: [.cursor/skills/foundry-run-evaluation/SKILL.md](../skills/foundry-run-evaluation/SKILL.md).

## Run record (CLI)

The Foundry CLI **does not write** steward `transcript.jsonl` under `.foundry/runs/{run_id}/`. Durable data is `snapshot.json`, `ledger.jsonl`, `artifacts/`, and `receipts/`.

Judgment tasks (`shape.examine`, `shape.present`, `shape.record`, …) store structured results in **`snapshot.agent_requests`** and **`ledger`** agent events — not in steward chat by default.

## User input

| Field | Source |
|---|---|
| `run_path` | `.foundry/runs/{run_id}` or archived `runs/{archive_slug}/` |
| `transcript_path` | Optional steward chat `.jsonl` (export or `archive/transcript.jsonl`) |
| `prior_review_path` | Optional prior review or `archive/review.md` |
| `focus` | Optional (`gates`, `judgment`, `operator-wait`, `steward-ux`, …) |
| `evaluation_id` | Optional (`review-1`, …) |

If the user `@`-mentions a run folder, use that as `run_path`. Transcript is **recommended** for user-gate reviews; **optional** for engine/judgment-only reviews.

For onboarding ergonomics retros (chat + artifacts, not formal scorecard), use **`/operator-onboarding-retro`**.

## Procedure

1. Confirm `run_path/snapshot.json` exists.
2. If `transcript_path` is given, confirm the file is readable.
3. Launch **run-evaluator** with all inputs (`transcript_path` may be `none` / omitted for artifacts-only).
4. Return `summary_markdown` in chat.
5. If `verdict` is `fail` or major findings exist, list top `recommendations` and `recommended_next_action` (from evaluator JSON).

## Evaluator launch prompt

```
Evaluate the Foundry run per your agent instructions and foundry-run-evaluation skill.

## Inputs

| Field | Value |
|---|---|
| run_path | {run_path} |
| transcript_path | {transcript_path or "none — artifacts_only"} |
| prior_review_path | {prior_review_path or "none"} |
| focus | {focus or "full evaluation"} |
| evaluation_id | {evaluation_id or "review-1"} |

## Task

Follow run-evaluator instructions. Investigate snapshot, ledger, artifacts, receipts, node contracts (judgment.md vs instructions.md), and transcript if provided. Return full JSON including summary_markdown, evaluation_mode, active_wait, and recommended_next_action.
```

For a **second opinion**, re-launch with a new `evaluation_id` and pass the first `summary_markdown` or file path as `prior_review_path`.

## Out of scope

| Action | Use when |
|---|---|
| Archiving after review | `/review-archive-run` |
| Modifying the run or re-running shape | User wants a redo |
| `foundry shape` (new run) | New shape run |
| `/craft-execute` | Continue implementation (only when shape is complete and authorized) |
| Fixing Foundry instructions | Separate implementation task |

## What good output looks like

- Scorecard: engine correctness, steward compliance (where applicable), judgment/deliverables (phase-scoped), operator information, communication (or N/A without transcript)
- `active_wait` and **recommended next action** matched to `wait.kind` (`answer`, `gate decide`, `run advance`, `/craft-execute`, …)
- Visit matrix with lifecycle/outcome per node touched
- Judgment quality notes from `agent_requests.*.accepted_result` when on task nodes
- Gate two-turn analysis **only** for user gates when transcript is available
- Clear verdict on whether the run state is trustworthy to **continue the current flow**
