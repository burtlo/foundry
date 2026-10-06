# Scheduled hygiene: engine gate instructions removal

**Status:** done  
**Goal:** Align older execute engine gates with forward policy and `verify.intake.gate` reference.

## Forward policy (from node-revision patterns)

**Engine gates** (`decider: engine`): no `nodes/{id}/instructions.md` and no `instructions:` in `factory-flow.yaml` when `render.py` already provides evidence + `run advance` guidance. Steward behavior lives in orchestration patterns + markdown packet sections only.

**User gates:** keep slim `instructions.md` (two-turn UX); do not duplicate plan/presentation loading that `render.py` already inlines.

## Reference pattern

`verify.intake.gate` — flow-only gate: `prompt`, lifecycle checks, `decider: engine`, **no** registry instructions file.

## Batch work items

| Node | Action |
|------|--------|
| `execute.intake.gate` | Remove `nodes/execute.intake.gate/instructions.md`; drop `instructions:` from flow; update catalog index + `node-instructions.mdc`; ensure `## Intake evidence` + `reads.intake_receipt` suffice; adjust acceptance/run_context if they assert Instructions section |
| `execute.test.gate` | Same for `execute.test.gate` / `## Test evidence` / `reads.test_receipt` |
| Inventory | `node-inventory.md` — engine gates documented as render-only steward UX |
| Tests | No scenarios requiring `## Instructions` on these engine gates |

## Non-goals

- Re-scope Shape or `execute.intake`–`execute.test.gate` behavior beyond instruction removal
- Change gate resolver logic in `gates.py`

## Verification

```bash
cd .cursor/foundry/cli
.venv/bin/python -m pytest tests/acceptance/test_execute_intake_gate.py tests/acceptance/test_execute_test_gate.py tests/acceptance/test_run_context.py -q
```

Single commit: `hygiene: drop engine gate instructions for execute intake/test gates`.
