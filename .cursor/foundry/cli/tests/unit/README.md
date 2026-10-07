# Foundry CLI unit tests

Flat `test_*.py` modules under this directory. Run via `foundry dev unit` or `pytest tests/unit`.

## Naming

| Pattern | Example | Covers |
|---------|---------|--------|
| `test_<module>.py` | `test_parser.py`, `test_run_store_durable.py` | `foundry_cli/<module>.py` (or cohesive package area) |
| `test_foundry_entrypoint.py` | — | Top-level `foundry.py` dispatch/formatters (not `foundry_config`) |
| `test_user_cli_shape.py` | — | User CLI: shape, answer, decide, status (`user_cli` shape surface) |
| `test_user_cli_execute.py` | — | User CLI: start, cancel, retry |
| `test_<node>_complete.py` | `test_execute_build_complete.py` | Node executor happy-path integration |
| `test_<node>_context.py` | `test_verify_intake_gate_context.py` | Context/markdown packet goldens |
| `test_<node>_gate_context.py` | `test_execute_test_gate_context.py` | Gate-specific context packets |
| `test_<node>_gate.py` | `test_execute_commit_gate.py`, `test_verify_intake_gate.py` | Gate resolution after advancing a fixture run |
| `test_deliver_stub_complete.py` | — | Full run completion at `deliver.stub` (stub execute/verify) |
| `test_execute_intake.py` | — | `execute.intake` advance + `execute.intake.gate` (fixture integration) |
| `test_execute_test_gate.py` | — | `execute.test.gate` pass/repair routing (stub execute) |
| `test_execute_repair_limit_gate.py` | — | `execute.repair.limit.gate` expressions and `on_examine` hook |

Shared advance helpers: `execute_advance_helpers.py`, `implementation_flow_helpers.py` (fixture workspace, `stub_record_gate_run`, authorize execute.start, advance through stub execute/verify).

Shape fixture chains: `shape_flow_helpers.py` (test workspace, intake → present → record).

Snapshot utilities: `snapshot_helpers.py` (`find_visit`, bounded `advance_run_steps`, `resolve_gate_at_node`).

Acceptance mirrors feature stems: see [tests/acceptance/README.md](../acceptance/README.md).

Support modules (not collected as tests): `conftest.py`, `constants.py`, `helpers.py`, `git_workspace.py`, `shape_flow_helpers.py`, `snapshot_helpers.py`, `receipt_fixtures.py`, `context_test_helpers.py`, `registry_test_helpers.py`, `execute_step_fixtures.py`, `execute_advance_helpers.py`, `implementation_flow_helpers.py`, `stub_execute_env.py`.
