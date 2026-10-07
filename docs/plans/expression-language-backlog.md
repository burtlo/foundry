# Expression language — backlog

Status: **open** (post implementation-flow release).

**Context:** Flow checks use `when` expressions evaluated by `evaluate_when_expression` in [routing.py](../../.cursor/foundry/cli/foundry_cli/engine/routing.py). Loop limits (`repair-within-limit`, `reverify-within-limit`) are implemented via [loop_limits.py](../../.cursor/foundry/cli/foundry_cli/engine/loop_limits.py), not ad-hoc substring matchers.

**Normative declaration:** [expressions.md](../concepts/expressions.md). **Shipped limits:** [flow-node-boundary-inventory.md](../features/flow-node-boundary-inventory.md).

## Decision (pick one track)

1. **Narrow documentation** — Document only supported fragments (status quo in `evaluate_when_expression`); reject or fail-closed on unsupported syntax in registry validation.
2. **Typed evaluator** — Implement a typed expression evaluator aligned with `expressions.md`; no new substring matchers in `routing.py`.

Do not add new special-case string matches in routing when a catalog check id can delegate to `loop_limits` or a dedicated helper.
