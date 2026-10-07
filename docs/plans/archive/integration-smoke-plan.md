# Operator integration smoke (Phase 6)

Status: **shipped**

**Program:** [operator-integration-program.md](../operator-integration-program.md)

## Scope

- Scripted smoke: in-repo judgment bridge (mocked Cursor SDK by default) + job host (`FOUNDRY_AGENT_ADAPTER=http`) + optional `--auto-advance` + `run create` / `run advance` through Shape to `shape.present.gate`.
- `just integration-smoke` (`python -m foundry_cli.operator_integration_smoke` from the CLI package).
- Unit test: `tests/unit/test_operator_integration_smoke.py`.

## Exit criteria

CI/local run completes without real API keys and asserts `active_node_id == shape.present.gate` with `wait_kind == decision`.

## Implementation

- `foundry_cli/operator_integration_smoke.py`
- [Operator runbook — integration smoke](../operator-runbook.md#integration-smoke)
