# Plan: `execute.repair.limit.gate` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [execute.test.gate contract cleanup](execute.test.gate-contract-cleanup-plan.md), engine gate reference `verify.intake.gate` (no `instructions.md`), generated [nodes/execute.repair.limit.gate.md](../nodes/execute.repair.limit.gate.md).

## Goal

`execute.repair.limit.gate` is an **engine-decider gate with no model worker**: repair routes from **execute.test.gate** and verify gates converge here; the engine admits the visit, enforces `repair-within-limit` on examine (escalate when over `config.limits.repair`), resolves **proceed** via `resolve_engine_gate` when within limit, seals, and routes to **execute.build** on the repair loop. The steward does **not** call `gate decide`; the host or steward invokes `run advance`.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None** — proceed is deterministic from ledger repair-loop count vs config limit |
| **Mechanism** | Engine: `_execute_repair_limit_gate_decision`, `resolve_engine_gate` on `run advance`, connection `on.decisions: [proceed]` with `loop: repair` |
| **Policy** | `repair-within-limit` on examine; `on_fail.action: escalate` |
| **Presentation** | Markdown context (`## Repair loop`); `reads.repair_loop` — **no** `instructions.md` |

Happy path:

```
repair route → admit execute.repair.limit.gate → on_examine repair-within-limit
  → opened → run advance → engine decision proceed → sealed → execute.build (repair loop)
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** No worker, no `judgment.md`.

## Minimal schema (factory-flow)

```yaml
  - id: execute.repair.limit.gate
    kind: gate
    title: Repair loop guard — count prior repair cycles before build
    produces:
      options:
      - proceed
    lifecycle:
      on_examine:
      - check: repair-within-limit
        on_fail:
          action: escalate
          reason: Repair loop limit reached
    decider: engine
```

No `instructions:`, `allow.*`, `worker`, or gate `receipts`.

## Gaps addressed

| Area | Fix |
|------|-----|
| No steward registry doc | `nodes/execute.repair.limit.gate/doc.yaml` |
| No context repair-loop read model | `reads.repair_loop` via `repair_loop_summary_for_snapshot` |
| No markdown evidence section | `## Repair loop` in `render.py` |
| Schema | `repairLoopSummary` on context packet `reads` |
| `node-instructions.mdc` | Execute repair limit gate row |
| Tests | Unit context/render; `test_engine_gates` exceed limit |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_execute_repair_limit_gate_context.py tests/unit/test_engine_gates.py tests/unit/test_execute_slice_2b.py -q -k "repair_limit or repair_loop"
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | Within limit, `run advance` seals gate with `proceed` and admits `execute.build` |
| AC2 | Over limit, `on_examine` escalates; resolver returns `REPAIR_LIMIT_EXCEEDED` |
| AC3 | `gate decide` on opened gate → `CAPABILITY_DENIED` (engine gate) |
| AC4 | JSON `run context`: `decider: engine`, `produces.options: [proceed]`, `reads.repair_loop` |
| AC5 | Markdown context: `## Repair loop`, `run advance`, no `gate decide`, no Instructions section |
| AC6 | No worker, no `allow.cli`, no `judgment.md`, no `instructions.md` |

## Stop condition

Stop after `execute.repair.limit.gate` — do not expand into verify gates or `execute.commit` except catalog references.
