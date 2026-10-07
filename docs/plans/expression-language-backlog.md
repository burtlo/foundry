# Expression language — backlog

Status: **track 2 chosen** — typed evaluator in `foundry_cli/engine/expressions.py` (Step 4 engine DSL plan).

**Context:** Flow checks use `when` expressions evaluated by `evaluate_when_expression` in [routing.py](../../.cursor/foundry/cli/foundry_cli/engine/routing.py). Loop limits (`repair-within-limit`, `reverify-within-limit`) are implemented via [loop_limits.py](../../.cursor/foundry/cli/foundry_cli/engine/loop_limits.py), not ad-hoc substring matchers.

**Normative declaration:** [expressions.md](../concepts/expressions.md). **Runtime:** [implementation-flow-runtime.md](../features/implementation-flow-runtime.md).

## Decision (pick one track)

**Chosen: track 2 (typed evaluator).** `evaluate_when_expression` delegates to `foundry_cli/engine/expressions.py`. Parity coverage: `tests/unit/test_expressions_parity.py` (table-driven from `flows/implementation/registry.yaml`).

1. **Narrow documentation** — Document only supported fragments; reject or fail-closed on unsupported syntax in registry validation. *(Not chosen.)*
2. **Typed evaluator** — Implement a typed expression evaluator aligned with `expressions.md`; no new substring matchers in `routing.py`. *(Shipped for implementation-flow `when` set.)*

Do not add new special-case string matches in routing when a catalog check id can delegate to `loop_limits` or a dedicated helper.
