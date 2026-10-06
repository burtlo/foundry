# Phase 1 — Extract deterministic Shape work

Status: **complete**

Related: [Phase 0 baseline](00-baseline.md), [job-host architecture](../job-host-architecture.md) (Shape proof), [deterministic extraction notes](../docs/shape-deterministic-extraction.md).

## Implemented

### Deterministic `shape.intake`

- **`visit intake complete`** CLI (`foundry_cli/engine/intake_executor.py`): captures verbatim `work_prompt`, builds ticket (`normalized_translation` null), assembles intake/agent receipts from ledger checks, publishes ticket, seals receipts, and transitions to `shape.examine` — **no `intake-checker.shape` worker**.
- Missing/empty `work_prompt`: structured `WORK_PROMPT_MISSING`, blocked intake receipt, sealed evidence, **no transition** (existing `INTAKE_BLOCKED` policy on manual `visit transition`).
- Removed **worker** binding from `factory-flow.yaml` `shape.intake`; added `visit.intake.complete` capability.
- Updated `nodes/shape.intake/operations.yaml` and `judgment.md` (judgment = app_folder confirmation + blocked UX only).
- Ticket schema: `normalized_translation` optional/nullable.

### `shape.examine` judgment surface

- `judgment.md` contains examination conversation guidance only; routing/seal mechanics remain in `operations.yaml` + engine.
- `examination_state.py`: engine derives `open_clarifying_questions_count` from `clarifying_questions` when present; routing `when:` expressions use derived count; state patch syncs counter when questions list is patched.

### Policy (unchanged, verified)

- `transition_policy.INTAKE_BLOCKED` on blocked intake receipt.
- Manifest validation on admit (`validate-manifest`); no model call on missing input.

## Acceptance criteria (Phase 1)

| Criterion | Status |
|-----------|--------|
| Intake advances without an agent on happy path | Met — `visit intake complete` + acceptance scenario |
| Examination agent-facing markdown is judgment-only | Met — `judgment.md` + context packet |
| Missing input stops without model; structured blocked path | Met — `WORK_PROMPT_MISSING` |
| Ticket schema allows nullable `normalized_translation` | Met |
| Tests updated; shape slice still passes | Met — see verification |

## Verification

From `.cursor/foundry/cli`:

```text
python -m pytest tests/unit/test_intake_executor.py tests/unit/test_examination_state.py tests/unit/test_transition_policy.py tests/unit/test_node_operations.py tests/unit/test_render.py -q
python -m pytest tests/acceptance/test_shape_*.py -q
```

## Out of scope (later phases)

- Full operations.yaml executor for all mechanism actions (intake complete is the first implemented slice).
- Replacing steward-patched `open_clarifying_questions_count` when `clarifying_questions` is absent (fallback to patched value retained).

*(Durable `advance()`, job host, model adapter, and `foundry shape` moved to Phases 2–5.)*
