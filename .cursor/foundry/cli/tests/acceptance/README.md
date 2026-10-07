# Foundry CLI acceptance tests

Gherkin behavioral contracts for the v1 CLI. **Source of truth:** `features/<stem>.feature`. Pytest loads them via `test_<stem>.py` (`scenarios("<stem>.feature")`). Step definitions live in `steps/<stem>.py` when not covered by `steps/common.py`; register new step modules in `tests/conftest.py` (`pytest_plugins`).

**Tags:** `@node.<node_id>` for node vertical slices; `@foundry.<area>` for cross-cutting CLI; `@workflow.execute.slice_*` for workflow-doc execute paths; `@cli.user` for steward commands. Meta scenarios in `dev_commands.feature` are excluded by default (`foundry dev acceptance` passes `-k "not dev_commands"`).

## Features

| Feature | Primary surface |
|---------|-----------------|
| `app_bootstrap.feature` | `app discover`, `app init`, `app validate` |
| `catalog_build.feature` | `catalog build` |
| `dev_commands.feature` | `dev docs`, `dev unit`, `dev acceptance`, `dev all` |
| `doc_build.feature` | `doc build` |
| `execute_intake_gate.feature` | `execute.intake.gate` slice |
| `execute_plan.feature` | `execute.plan` slice |
| `execute_slice_2a.feature` | Workflow-02 execute slice 2A (host path) |
| `execute_slice_2b.feature` | Workflow-02 execute slice 2B (build/test/repair) |
| `execute_test_gate.feature` | `execute.test.gate` slice |
| `foundry_config.feature` | `config init`, `config validate`, `cli resolve` |
| `job_host.feature` | Persistent local job host |
| `run_archive.feature` | `run archive` |
| `run_context.feature` | `run context` (context packet contracts) |
| `run_storage.feature` | Durable run storage and host idempotency |
| `shape_examine.feature` | `shape.examine` slice |
| `shape_examine_gate.feature` | `shape.examine.gate` slice |
| `shape_intake.feature` | `shape.intake` slice |
| `shape_phase_e2e.feature` | Shape phase through `execute.start` |
| `shape_present.feature` | `shape.present` slice |
| `shape_present_gate.feature` | `shape.present.gate` slice |
| `shape_record.feature` | `shape.record` slice |
| `shape_record_gate.feature` | `shape.record.gate` slice |
| `user_cli.feature` | `shape`, `status`, `attach`, supervision commands |

## Run

```bash
cd .cursor/foundry/cli
.venv/bin/python foundry.py --workspace ../../.. dev acceptance
```

Or: `./run_acceptance.sh`

Porcelain run fixtures under `.cursor/foundry/fixtures/runs/` can be regenerated with:

```bash
python scripts/build_porcelain_run_fixtures.py
```

(run from `.cursor/foundry/cli` with the project venv). Use `pytest tests/acceptance/...` directly when debugging failures; `foundry dev acceptance` prints pytest output on failure.

Workflow concepts live in `docs/concepts/`. CLI reference pages under `docs/cli/` are generated as commands ship (`foundry dev docs`).

Unit test naming and workflow slices: [tests/unit/README.md](../unit/README.md).
