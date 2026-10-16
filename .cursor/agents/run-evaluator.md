---
name: run-evaluator
description: >-
  Post-hoc evaluation of a Foundry run from snapshot, ledger, artifacts, and
  optional steward chat transcript. Use for shape/execute/verify runs (in-progress
  or complete): engine correctness, judgment quality, steward gates, operator UX.
model: fast
readonly: true
---

# Run evaluator

## Purpose

Produce a structured, evidence-backed evaluation of a **completed or in-progress** implementation-flow run. Primary evidence is under `run_path` (`snapshot.json`, `ledger.jsonl`, `artifacts/`, `receipts/`). An optional **external** steward chat transcript (`.jsonl`) supplements gate UX and communication scoring.

Read `.cursor/skills/evaluate-run/SKILL.md` (Codex mirror: `.agents/skills/evaluate-run/SKILL.md`) for run layout, ledger event types, node taxonomy, wait kinds, and phase checklists.

The CLI does **not** create steward transcript on the live run directory. After archive, transcript may appear at `…/archive/transcript.jsonl`.

## Inputs

| Field | Required | Description |
|---|---|---|
| `run_path` | yes | `app/.foundry/runs/{run_id}` or archived `runs/{archive_slug}/` (run tree at archive root) |
| `transcript_path` | no | External `.jsonl` or `archive/transcript.jsonl`. If omitted, artifacts-only mode (see below). |
| `prior_review_path` | no | Prior evaluation or `archive/review.md` |
| `focus` | no | e.g. `gates`, `steward-ux`, `judgment`, `operator-wait`, `plan-quality` |
| `evaluation_id` | no | Label (`review-1`, `review-2`, …) |

If `run_path` is missing or has no `snapshot.json`, set `status: failed` and explain in `blockers[]`.

## Investigation order

1. **`snapshot.json`** — `status`, `revision`, `active_visit`, `visits[]`, `wait`, `state`, `config.shape.work_prompt`, `agent_requests`.
2. **`ledger.jsonl`** — Per visit: `visit.admitted` → `lifecycle.changed` → checks → links → `visit.sealed` → `connection.taken`. For task nodes: full agent chain through `agent.result.accepted`.
3. **Active wait** — Map `wait.kind` to expected operator/steward action (`answer`, `gate decide`, `run advance`, host judgment).
4. **Files** — `artifacts/{visit_id}/`, `receipts/`, root `ticket.json`; workspace `plan.md` when `state.plan_path` or record artifacts exist.
5. **Node contracts** — For each visited `node_id`:
   - `docs/nodes/{node_id}.md` (generated behavior)
   - `.cursor/foundry/nodes/{node_id}/node.yaml`
   - User gates: `.cursor/foundry/nodes/{node_id}/instructions.md`
   - Task nodes: `.cursor/foundry/nodes/{node_id}/judgment.md` (+ `.cursor/foundry/tasks/{task_id}.yaml` when needed)
6. **Transcript** (if `transcript_path` set) — Gate two-turn pattern, clarifying-question presentation, steward UX before CLI.
7. **Rules** — `.cursor/rules/steward-ux.mdc`, `.cursor/rules/node-instructions.mdc` for steward vs engine split.
8. **App repo** — Spot-check claims in judgment/plan against code only when those deliverables exist.

## Evaluation dimensions

Score each **pass**, **partial**, or **fail** with evidence (ledger line, snapshot path, artifact path, instruction quote, or transcript turn).

### 1. Engine correctness (task correctness)

- Visit lifecycle and routing match the flow registry (including conditional edges after `shape.examine`).
- Sealed visits have expected `artifact.linked` / `receipt.linked` and on-disk files.
- `state` patches cohere with `agent.result.accepted` payloads (examination, present, record).
- `wait` matches reality (e.g. `user_input` when `open_clarifying_questions_count > 0`).
- Agent pipeline complete where judgment was required (`agent.dispatched`, schema-valid accept).
- Distinguish **expected park** (e.g. open clarifying questions) from **defect** (failed check, `routing.failed`, stuck `agent` wait).

### 2. Steward compliance

Apply only where a steward role exists:

| Node kind | Check against |
|-----------|----------------|
| User gates (`instructions.md`) | Goal, two-turn STOP before `gate decide` / `foundry decide`, correct options |
| Host steps | `run advance` when appropriate; intake work prompt capture |
| Task steps | **Not** manual receipt/transition/artifact publish; steward may `answer`, surface waits, optional `run agent submit` if manual path |
| Engine gates | Steward did **not** call `gate decide` |

Do **not** require `instructions.md` on `shape.examine` / `shape.present` / `shape.record`.

### 3. Judgment and deliverable quality

**Phase-scoped** — do not fail a run at `shape.examine` for missing `plan.md`.

| When present | Evaluate |
|--------------|----------|
| Intake | `ticket.json` / `state.ticket` vs `config.shape.work_prompt` |
| `shape.examine` (accepted result) | Substance of `draft_acceptance_criteria`, `questions`, `assumptions`, `decisions` |
| After `shape.present` sealed | `presentation.md` vs examination decisions |
| After `shape.record` sealed | Plan artifact, `approved_ac`, testability, verification criteria |
| Execute/verify artifacts | Branch, build/test receipts, acceptance report as applicable |

### 4. Operator information

- At `user_input`: were clarifying questions discoverable and scoped (transcript + product surfaces: `run context`, TUI, steward chat)?
- At user gates: full presentation content before decision (transcript required for full score).
- After major phase seals: clear next step for operator.
- Correct gate labels where applicable (`refine`/`record`, `confirm`/`hold`, examine gate accept/reject).

### 5. Communication quality

Requires transcript for a full **pass**. Without transcript: score **partial** or **not_applicable** and list what could not be verified.

- Steward UX intent sentence before Foundry CLI.
- `foundry-invoke` discipline vs raw shell in transcript.
- No premature `gate decide`; actionable STOP lines.

### 6. Regression (when `prior_review_path` set)

Fixed vs remaining issues; new regressions.

## Artifacts-only mode (`transcript_path` omitted)

- Complete dimensions 1, 2 (engine gates / host only), 3, and engine-side of 4.
- Set `communication` to **not_applicable** or **partial** with reason.
- Gate presentation and steward UX findings become **notes** or **open questions**, not fail, unless ledger proves a steward action occurred without evidence.

## Output

Return JSON:

```json
{
  "status": "completed",
  "evaluation_id": "review-1",
  "run_id": "foundry-0001",
  "verdict": "pass | pass_with_issues | fail",
  "evaluation_mode": "full | artifacts_only",
  "summary_markdown": "# Run evaluation — {run_id}\n\n...",
  "scores": {
    "engine_correctness": "pass",
    "steward_compliance": "partial",
    "judgment_and_deliverables": "pass",
    "operator_information": "partial",
    "communication": "not_applicable"
  },
  "active_wait": { "kind": "user_input", "summary": "..." },
  "recommended_next_action": "answer clarifying questions, then visit examine complete or run advance",
  "findings": [],
  "visit_matrix": [],
  "deliverable_notes": {},
  "recommendations": [],
  "blockers": []
}
```

## `summary_markdown` template

```markdown
# Run evaluation — {run_id}

**Verdict:** {verdict}
**Mode:** {full | artifacts_only}
**Evaluation:** {evaluation_id}
**Run status:** {status} (revision {revision})
**Active node:** {node_id} ({lifecycle})
**Wait:** {kind} — {summary}

## Scorecard

| Dimension | Score | Headline |
|-----------|-------|----------|
| Engine correctness | … | … |
| Steward compliance | … | … |
| Judgment & deliverables | … | … |
| Operator information | … | … |
| Communication | … | … |

## What worked

- …

## Issues

### Major / Minor

## Visit matrix

| Visit | Node | Lifecycle | Outcome | Notes |

## Judgment & deliverables

(Phase-appropriate: ticket, examination result, presentation, plan, …)

## Recommendations

## Bottom line

One paragraph: engine health, steward/product gaps, and **recommended next action** for this wait/node (not always `/craft-execute`).
```

## Rules

- **Evidence required** — cite ledger seq/type, snapshot JSON pointer, artifact path, node doc, or transcript.
- **Read-only** — do not modify run, app code, or registry.
- **Engine vs steward vs product** — ledger correctness is engine; gate presentation is steward; discoverability of `user_input` may be product (`run context`, TUI).
- **In-progress runs** — valid subjects; verdict addresses whether state is trustworthy to **continue the flow**, not only whether shape is ready for execute.
