# Plan: `execute.commit.gate` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [execute.commit contract cleanup](execute.commit-contract-cleanup-plan.md), engine gate reference `execute.repair.limit.gate` (no `instructions.md`), generated [nodes/execute.commit.gate.md](../nodes/execute.commit.gate.md).

## Goal

`execute.commit.gate` is an **engine-decider gate with no model worker**: after `execute.commit` seals with `final-commit` and a commit-agent receipt, the engine admits the visit, enforces `prior-execute-commit-sealed`, `final-commit-recorded`, and `reverify-within-limit` on examine, resolves **pass** via `resolve_engine_gate` when `final_commit_sha` is set and the sealed visit exists, seals, and routes to **verify.intake**. The steward does **not** call `gate decide`; the host or steward invokes `run advance`.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None** — pass is deterministic from run state and sealed execute.commit evidence |
| **Mechanism** | Engine: `_execute_commit_gate_decision`, `resolve_engine_gate` on `run advance`, connection `on.decisions: [pass]` |
| **Policy** | `final-commit-recorded` on examine; missing SHA or unsealed commit step → gate cannot pass (`EVIDENCE_MISSING`) |
| **Presentation** | Markdown context (`## Commit evidence`); `reads.commit_receipt` + `reads.state.final_commit_sha` — **no** `instructions.md` |

Happy path:

```
execute.commit sealed (final_commit_sha + commit-agent receipt) → admit execute.commit.gate → on_examine checks
  → opened → run advance → engine decision pass → sealed → verify.intake
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** No worker, no `judgment.md`.

## Minimal schema (flow registry)

```yaml
  - id: execute.commit.gate
    kind: gate
    title: Execute commit recorded
    produces:
      options:
      - pass
    prompt: Machine gate. Final execute.commit must record a commit on the feature branch (empty commit allowed).
    lifecycle:
      on_examine:
      - check: reverify-within-limit
        on_fail:
          action: escalate
          reason: Re-verify loop limit reached
      - check: prior-execute-commit-sealed
      - check: final-commit-recorded
    decider: engine
```

No `instructions:`, `allow.*`, `worker`, or gate `receipts`.

## Gaps addressed

| Area | Fix |
|------|-----|
| No steward registry doc | `nodes/execute.commit.gate/doc.yaml` |
| No context commit read model | `reads.commit_receipt` via `commit_receipt_summary_for_sealed_step`; state SHA/message on gate |
| No markdown evidence section | `## Commit evidence` in `render.py` |
| Schema | `commit_receipt` on context packet `reads` (same shape as `test_receipt`) |
| `node-instructions.mdc` | Execute commit gate row |
| Tests | Unit context/render; `test_engine_gates` pass and missing-evidence cases |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_execute_commit_gate_context.py tests/unit/test_engine_gates.py tests/unit/test_workflow_slices_2c_2f.py -q -k "commit_gate or execute_commit_gate"
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | With `final_commit_sha` and sealed `execute.commit`, `resolve_engine_gate` returns `pass` |
| AC2 | Missing `final_commit_sha` or unsealed commit visit → `EVIDENCE_MISSING` |
| AC3 | `gate decide` on opened gate → `CAPABILITY_DENIED` (engine gate) |
| AC4 | JSON `run context`: `decider: engine`, `produces.options: [pass]`, `reads.commit_receipt`, `reads.state.final_commit_sha` when set |
| AC5 | Markdown context: `## Commit evidence`, `run advance`, no `gate decide`, no Instructions section |
| AC6 | No worker, no `allow.cli`, no `judgment.md`, no `instructions.md` |

## Stop condition

Stop after `execute.commit.gate` — do not expand into verify intake except catalog references.
