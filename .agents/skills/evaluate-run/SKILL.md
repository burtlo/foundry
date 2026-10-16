---
name: evaluate-run
description: >-
  Evaluates a Foundry run from snapshot, ledger, artifacts, and optional steward
  chat transcript. Covers engine correctness, judgment quality, steward gates,
  operator waits, and phase-appropriate deliverables. Use after shape, execute,
  or verify — including in-progress runs parked on agent or user_input waits.
disable-model-invocation: true
---

# Evaluate run

Role: evaluation lead — launch **run-evaluator** and return a structured review.

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

For product-feedback retros (chat + artifacts, not formal scorecard), use **`/capture-product-feedback`**.

## Procedure

1. Confirm `run_path/snapshot.json` exists.
2. If `transcript_path` is given, confirm the file is readable.
3. Launch **run-evaluator** with all inputs (`transcript_path` may be `none` / omitted for artifacts-only).
4. Return `summary_markdown` in chat.
5. If `verdict` is `fail` or major findings exist, list top `recommendations` and `recommended_next_action` (from evaluator JSON).

## Evaluator launch prompt

```
Evaluate the Foundry run per your agent instructions and evaluate-run skill.

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

---

# Run record reference

Evaluate runs from **engine evidence first** (`snapshot.json`, `ledger.jsonl`, `artifacts/`, `receipts/`). An external steward chat transcript (`.jsonl`) is optional and mainly needed for gate two-turn compliance and steward UX — the CLI does **not** write `transcript.jsonl` under `.foundry/runs/{run_id}/`.

Concept reference: [docs/concepts/run-record.md](docs/concepts/run-record.md). Generated node contracts: `docs/nodes/{node_id}.md`.

## Run directory inventory (read order)

| Priority | Path | Use |
|----------|------|-----|
| 1 | `snapshot.json` | `status`, `revision`, `active_visit`, `visits[]`, `wait`, `state`, `config` (incl. `config.shape.work_prompt`), `agent_requests` |
| 2 | `ledger.jsonl` | Event order; replay authority if snapshot is stale |
| 3 | `ticket.json` (run root) | Intake mirror; also `artifacts/{visit_id}/ticket.json` |
| 4 | `artifacts/{visit_id}/` | Sealed visit outputs (`presentation.md`, plan, branch diff, …) |
| 5 | `receipts/` | Intake/agent receipts, host `assessment.md` where present |
| 6 | `archive/manifest.json` | If archived under `runs/{app_id}-NNNN/` |

CLI helpers: `run get`, `status`, `run context --markdown`, `ledger show`, `run events`, `foundry tui` (host client for `user_input` / gates).

## Snapshot fields evaluators care about

- **`wait`**: `kind` (`agent`, `user_input`, `decision`, `operator`), `summary`, `request_ref`, `visit_id`
- **`agent_requests`**: per `request_id` — `status`, `task_id`, `accepted_result`, `provider_request_id` (`run-*` = bridge, `stub_*` = stub adapter)
- **`state`**: shape — `ticket`, `draft_ac`, `clarifying_questions`, `open_clarifying_questions_count`, `assumptions`, `examination_decisions`, `approved_ac`, `plan_path`; execute — `feature_branch`, …
- **Visits**: `lifecycle` (`opened` / `sealed`), `outcome`, `node_id`

## Ledger events that prove behavior

| `type` | Proves |
|--------|--------|
| `run.snapshot.checkpoint` | Materialized snapshot at `payload.materialized` |
| `run.status_changed` | Run status transitions |
| `visit.admitted` / `lifecycle.changed` / `visit.sealed` | Visit lifecycle |
| `check.recorded` / `policy.applied` | Hook checks and engine policy |
| `artifact.linked` / `receipt.linked` | Published outputs |
| `connection.taken` | Routing (note `loop` on repair paths) |
| `agent.requested` → `agent.dispatch.outbox` → `agent.dispatched` → `agent.result.accepted` | Judgment task pipeline |
| `agent.result.rejected` / `agent.result.superseded` | Failed judgment or new examine round after `answer` |
| `user.input.submitted` | Clarifying answers recorded |
| `gate.presented` / `gate.resolved` | User or engine gates |

## Node taxonomy (implementation flow)

| Pattern | Examples | Steward surface | Model / engine |
|---------|----------|-----------------|----------------|
| Engine `host` step | `shape.intake`, `execute.intake`, `execute.build`, `execute.test`, … | `run advance`; optional `visit state patch` on intake | Mechanisms in `operations.yaml`; artifacts/receipts on seal |
| `task` + `judgment.md` | `shape.examine`, `shape.present`, `shape.record`, `execute.plan`, `verify.acceptance` | `answer` (examine Q&A); `visit * complete` or `run advance`; optional `run agent submit` if not host-dispatched | Bridge/stub judgment; engine patches state, sets `wait`, seals on complete |
| User gate + `instructions.md` | `shape.examine.gate`, `shape.present.gate`, `shape.record.gate`, `execute.start`, `verify.code_review.gate`, `verify.complete.gate` | Two-turn presentation then `gate decide` / `foundry decide` | Engine checks + `gate.resolved` |
| Engine gate | `execute.test.gate`, `verify.acceptance.gate`, … | **No** manual `gate decide` — `run advance` only | Auto `gate.resolved` from evidence |

**Instruction paths:** task nodes use `.cursor/foundry/nodes/{node_id}/judgment.md` (and `.cursor/foundry/tasks/{task_id}.yaml`). User gates use `instructions.md`. `shape.intake` has no steward step file.

**Routing after `shape.examine` sealed:** `state.open_clarifying_questions_count == 0` → `shape.present`; else → `shape.examine.gate` (or operator answers via `answer` and may re-dispatch judgment).

## Wait kind → operator / steward expectation

| `wait.kind` | Meaning | Judge |
|-------------|---------|--------|
| `agent` | Judgment in flight or awaiting submit | Ledger agent chain; result in `agent_requests` |
| `user_input` | Open clarifying questions (`request_ref` like `questions:{visit_id}`) | Questions in `state.clarifying_questions`; steward should surface them; operator uses `answer` or TUI |
| `decision` | User gate | Transcript for two-turn pattern; `gate.resolved` in ledger |
| `operator` | Missing work prompt or blocked intake | Steward supplies prompt or recovery per runbook |

## Phase-specific checks (abbreviated)

**After intake sealed:** `visit.sealed` completed; `artifact.linked` ticket; intake + agent receipts; `validate-manifest` pass; `state.ticket` matches `config.shape.work_prompt`.

**During `shape.examine`:** If `user_input` — open questions count, judgment quality in `accepted_result`; parking is **expected**, not failure. If `agent` — dispatch completed and schema-valid accept.

**After shape record sealed:** run `plan.md` artifact, `approved_ac` in state; then execute authorization at `execute.start`.

**Execute/verify:** Distinguish host steps (`run advance`) from engine gates (no steward decide). Count repair loops via `connection.taken` + `loop`.

## Do not use the old evaluation model

| Wrong | Right |
|-------|--------|
| Require steward `instructions.md` on task nodes | `judgment.md` + `docs/nodes/{node}.md` |
| Expect steward-authored examination JSON without `agent.result.accepted` | Trace AC/questions to accepted agent result |
| Score `shape.steward` receipt on `shape.examine` | Agent receipt sealed on `visit examine complete` |
| Expect steward `artifact publish` / `receipt seal` on task steps | Engine on `visit.*.complete` / advance |
| `gate decide` on engine gates | `run advance` only |
| Fail in-progress run for missing plan/presentation | Score deliverables only for sealed visits that produce them |
| Bottom line always `/craft-execute` | Map to current `wait` and active node (e.g. `answer`, gate, `craft-execute`) |

## Transcript role

| Artifacts alone | Transcript adds |
|-----------------|-----------------|
| Progression, routing, judgment content, schema validity | Gate presentation before decide |
| Wait correctness | Steward intent sentences, premature CLI |
| Engine vs product UX gaps | Whether questions were shown clearly |

If no transcript: run **artifacts-only** evaluation; mark communication / gate UX dimensions **partial** or **not_applicable** with explicit gaps.

## Archive

`foundry run archive` moves/copies the run tree to `{foundry_repo}/runs/{app_id}-NNNN}/`, adds `archive/manifest.json`, optional `archive/transcript.jsonl` and `archive/review.md`. Original `run_id` preserved in manifest.
