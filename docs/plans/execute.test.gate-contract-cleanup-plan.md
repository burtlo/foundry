# Plan: `execute.test.gate` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [execute.test contract cleanup](execute.test-contract-cleanup-plan.md), engine gate reference [execute.intake.gate contract cleanup](execute.intake.gate-contract-cleanup-plan.md), generated [nodes/execute.test.gate.md](../nodes/execute.test.gate.md).

## Goal

`execute.test.gate` is an **engine-decider gate with no model worker**: the engine admits the visit after sealed **execute.test**, resolves **pass** or **repair** from the sealed agent receipt `commands[]` exit codes via `resolve_engine_gate`, seals, and routes to **execute.commit** or **execute.repair.limit.gate**. The steward does **not** call `gate decide`; the host or steward invokes `run advance`.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None** — pass/repair is deterministic from receipt exit codes |
| **Mechanism** | Engine: `_execute_test_gate_decision`, `resolve_engine_gate` on `run advance`, connections `on.decisions: [pass]` / `[repair]` |
| **Policy** | `prior-execute-test-sealed` on examine |
| **Presentation** | Steward `instructions.md` + markdown context (`## Test evidence`, inlined instructions); `reads.test_receipt` summary |

Happy path:

```
execute.test sealed (agent receipt) → admit execute.test.gate → on_examine checks
  → opened → run advance → engine decision pass|repair → sealed → execute.commit | execute.repair.limit.gate
```

**Agent necessity (Step 6):** **A — Fully deterministic engine node.** No worker, no `judgment.md`.

## Runtime sequence (Step 1)

1. `execute.test` seals with outcome `completed` and linked agent receipt (`commands[]` exit codes).
2. Connection to `execute.test.gate`; visit admitted → `on_examine`: `prior-execute-test-sealed`.
3. `on_open` → lifecycle `opened`; no user decision wait.
4. `run advance` → `resolve_engine_gate` → `_execute_test_gate_decision` reads receipt from sealed `execute.test` visit.
5. All command exit codes `0` → decision `pass`, route to `execute.commit`.
6. Any non-zero exit code → decision `repair`, route to `execute.repair.limit.gate`.

## Minimal schema (Step 9)

```yaml
  - id: execute.test.gate
    kind: gate
    title: Execute test pass
    instructions: registry:nodes/execute.test.gate/instructions.md
    reads:
      state:
      - last_test_exit_code
    produces:
      options:
      - pass
      - repair
    prompt: Engine gate. Maps sealed execute.test agent receipt command exit codes to pass or repair.
    lifecycle:
      on_examine:
      - check: prior-execute-test-sealed
    decider: engine
```

No `allow.*`, `worker`, or gate `receipts`.

## Gaps addressed

| Area | Fix |
|------|-----|
| Stale flow `prompt` (machine gate wording) | Engine-oriented prompt |
| No steward registry assets | `nodes/execute.test.gate/instructions.md`, `doc.yaml` |
| No context `reads.test_receipt` / evidence section | `assemble_context` + `## Test evidence` in `render.py` |
| No dedicated acceptance tag | `@node.execute.test.gate` feature + `run_context` scenario |
| Catalog index tests list | `catalog build` sync |
| `node-instructions.mdc` | Execute test gate row |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/acceptance/test_execute_test_gate.py tests/unit/test_execute_test_gate_context.py tests/unit/test_engine_gates.py -q
pytest tests/acceptance/test_run_context.py -q -k "execute.test.gate"
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | After passing `execute.test`, `run advance` seals gate with `pass` and admits `execute.commit` |
| AC2 | Failed verification receipt → `run advance` seals gate with `repair` and admits repair limit gate |
| AC3 | `gate decide` on opened gate → `CAPABILITY_DENIED` (engine gate) |
| AC4 | JSON `run context`: `decider: engine`, `produces.options: [pass, repair]`, `reads.test_receipt`, instructions ref |
| AC5 | Markdown context: inlined instructions, `run advance`, `## Test evidence`, no `gate decide` |
| AC6 | No worker, no `allow.cli`, no `judgment.md` |

## Stop condition

Stop after `execute.test.gate` — do not expand into `execute.repair.limit.gate` except catalog test list references.
