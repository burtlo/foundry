# Verify acceptance — judgment

## Purpose

Judge whether sealed **approved acceptance criteria** are satisfied using execute evidence: branch diff, test exit code, shape plan, and commit context. Produce a single structured result; do not call CLI or choose the next workflow node.

## Policy (apply in priority order when setting `gate_decision`)

1. **reshape** — AC scope wrong, missing, or contradictory.
2. **replan** — AC OK but execution graph / plan does not cover required work.
3. **rework_execute** — Plan OK but implementation, diff, or tests insufficient.
4. **pass** — All criteria `met`, tests OK where required, diff scope OK, `evidence_ok: true`.

When multiple rows apply, choose the **most severe** (lowest number). `pass` only when no row 1–3 applies.

## Output (schema-bound only)

- `items` — per-criterion judgment (`met` | `not_met` | `not_verified`) with `criterion` text and `basis` tied to evidence refs when `met`.
- `gate_decision` — one of `pass`, `replan`, `reshape`, `rework_execute`.
- `evidence_ok` — `true` only when every criterion is `met` with cited evidence; otherwise `false`.
- `summary` — short narrative of the validation.

`met` requires explicit rationale tied to evidence (diff hunk, test output, artifact id). Do not treat diff comment substrings as proof of behavioral satisfaction. Non-zero `last_test_exit_code` blocks test-backed `met` claims.

The host publishes `verify-findings`, seals the agent receipt, and routes at `verify.acceptance.gate`.
