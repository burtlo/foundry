# Plan: `execute.intake.gate` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node review prompt](workflow-node-review-prompt.md), upstream [execute.intake contract cleanup](execute.intake-contract-cleanup-plan.md) (**done**), user-gate patterns [shape-present-gate-contract-cleanup-plan](shape-present-gate-contract-cleanup-plan.md) and [execute.start contract cleanup](execute.start-contract-cleanup-plan.md), generated [nodes/execute.intake.gate.md](../nodes/execute.intake.gate.md).

## Goal

`execute.intake.gate` is an **engine-decider gate with no model worker**: the engine admits the visit, enforces prerequisites (`prior-execute-intake-sealed`, `intake-receipt-sealed` on the sealed `execute.intake` visit), resolves **pass** from the intake receipt status via `resolve_engine_gate`, seals, and routes to `execute.branch`. The steward does **not** call `gate decide`; the host or steward invokes `run advance` to close the gate.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None** — pass/blocked is deterministic from sealed intake receipt |
| **Mechanism** | Engine: `_execute_intake_gate_decision`, `resolve_engine_gate` on `run advance`, connection `on.decisions: [pass]` |
| **Policy** | `intake-receipt-sealed` on examine (prior visit receipt), blocked receipt → gate cannot pass (`EVIDENCE_MISSING`) |
| **Presentation** | Steward `instructions.md` + markdown context (`## Intake evidence`, inlined instructions); optional user visibility when intake was blocked upstream |

Happy path:

```
execute.intake sealed (passed receipt) → admit execute.intake.gate → on_examine checks
  → opened → run advance → engine decision pass → sealed → execute.branch
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** No worker, no `judgment.md`. Semantic judgment already happened at `execute.intake` validation.

## Runtime sequence (Step 1)

1. `execute.intake` seals with outcome `completed` and linked intake receipt `status: passed`.
2. Connection to `execute.intake.gate`; visit admitted → `on_examine`: `prior-execute-intake-sealed`, `intake-receipt-sealed` (receipt visit id resolved to latest sealed `execute.intake` — `routing.py`).
3. `on_open` → lifecycle `opened`; no user decision wait.
4. `run advance` → `resolve_engine_gate` → `_execute_intake_gate_decision` reads receipt from sealed `execute.intake` visit.
5. On `passed` → decision `pass`, seal, route to `execute.branch`.
6. On `blocked`/`failed`/missing receipt → advance does not pass gate (`EVIDENCE_MISSING`).

## Minimal schema (Step 9)

```yaml
  - id: execute.intake.gate
    kind: gate
    title: Execute intake blocked check
    instructions: registry:nodes/execute.intake.gate/instructions.md
    reads:
      state:
      - intake_path
    produces:
      options:
      - pass
    prompt: Engine gate. Confirms the sealed execute.intake receipt status is passed before branching.
    lifecycle:
      on_examine:
      - check: prior-execute-intake-sealed
      - check: intake-receipt-sealed
        on_fail:
          action: halt
          reason: Intake receipt failed
    decider: engine
```

No `allow.*`, `worker`, or `receipts` on the gate entry.

## Gaps addressed

| Area | Fix |
|------|-----|
| Stale flow `prompt` (agent assessment wording) | Updated prompt text |
| No steward registry assets | `nodes/execute.intake.gate/instructions.md`, `doc.yaml` |
| No context `decider` / intake evidence | `assemble_context` adds `decider`; `reads.intake_receipt` summary for gate |
| No acceptance tag | `@node.execute.intake.gate` feature + `run_context` scenario |
| Catalog index empty tests/assets | `catalog build` sync |
| `node-instructions.mdc` | Execute intake gate row |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/acceptance/test_execute_intake_gate.py tests/acceptance/test_run_context.py -q -k "intake_gate or execute.intake.gate"
pytest tests/unit/test_engine_gates.py tests/unit/test_execute_intake.py -q
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | After passed `execute.intake`, `run advance` seals gate with `pass` and admits `execute.branch` |
| AC2 | `gate decide` on opened gate → `CAPABILITY_DENIED` (engine gate) |
| AC3 | Blocked intake receipt → resolver `ok: false` (`EVIDENCE_MISSING`) |
| AC4 | JSON `run context`: `decider: engine`, `produces.options: [pass]`, `reads.intake_receipt.status`, instructions ref |
| AC5 | Markdown context: inlined instructions, `run advance`, no `gate decide` |
| AC6 | No worker, no `allow.cli`, no `judgment.md` |

## Stop condition

Stop after `execute.intake.gate` — do not expand into `execute.branch` except catalog test list references.
