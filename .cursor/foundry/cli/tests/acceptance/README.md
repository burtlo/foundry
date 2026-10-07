# Foundry CLI acceptance tests

Gherkin behavioral contracts for the v1 CLI. **Source of truth:** `features/<stem>.feature`. Pytest loads them via `test_<stem>.py` (`scenarios("<stem>.feature")`). Step definitions live in `steps/<stem>.py` when not covered by `steps/common.py`; register new step modules in `tests/conftest.py` (`pytest_plugins`).

**Tags:** `@node.<node_id>` for node vertical slices; `@foundry.<area>` for cross-cutting CLI; `@cli.user` for steward commands. Meta scenarios in `dev_commands.feature` are excluded by default (`foundry dev acceptance` passes `-k "not dev_commands"`).

**Invokes:** `When I invoke "run create"` (and similar) always run the CLI with `--json` in the harness; feature text omits that flag. Use `with markdown output` only for steward markdown packets (`run context`).

**Assertions:** `Then the CLI succeeds` / `Then the CLI succeeds with:` (response envelope fields) / `Then the CLI fails with error "CODE"` for expected failures. Keep `context fields match:` for `run context` packet bodies. `Then the CLI exit code is N` remains for non-envelope cases (e.g. argparse exit `2`).

## Features

| Feature | Primary surface |
|---------|-----------------|
| `app_bootstrap.feature` | `app discover`, `app init`, `app validate` |
| `catalog_build.feature` | `catalog build` |
| `dev_commands.feature` | `dev docs`, `dev unit`, `dev acceptance`, `dev all` |
| `doc_build.feature` | `doc build` |
| `execute_intake_gate.feature` | `execute.intake.gate` slice |
| `execute_plan.feature` | `execute.plan` slice |
| `execute_start_local.feature` | Local `start` after record gate reaches `execute.build` |
| `execute_stub_to_verify_intake.feature` | Stub execute forward path reaches `verify.intake` |
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

## Layout

| Pattern | Example | Role |
|---------|---------|------|
| `features/<stem>.feature` | `shape_examine.feature` | Gherkin source of truth |
| `test_<stem>.py` | `test_shape_examine.py` | `scenarios("<stem>.feature")` loader |
| `steps/<stem>.py` | `steps/shape_examine.py` | Step definitions (register in `tests/conftest.py`) |
| `steps/common.py` | — | Shared Given/When/Then for CLI invoke and context assertions |

## Support modules (not collected by pytest)

| Module | Reuses from `tests/unit/` | Purpose |
|--------|---------------------------|---------|
| `helpers.py` | — | Stateful `invoke_foundry(acceptance)`, snapshot/JSON path helpers |
| `constants.py` | `constants.py` (schema URIs, shared error codes) | Acceptance-specific fixture names and CLI command labels |
| `conftest.py` | — | `acceptance` dict fixture |
| `acceptance_invoke.py` | — | `invoke_acceptance_command`, `reset_acceptance_invoke_argv` (steps → `helpers.invoke_foundry`) |
| `acceptance_agent_steps.py` | — | Agent wait/submit, visit lifecycle complete, local `run advance` |
| `acceptance_flow_helpers.py` | `implementation_flow_helpers`, `git_workspace` | Porcelain install, execute workspace prep, advance to `execute.plan` |
| `acceptance_shape_judgments.py` | `shape_flow_helpers`, `execute_advance_helpers` | PROCEED/BLOCKED payloads for shape present/record and execute.plan |
| `acceptance_intake_drafts.py` | — | On-disk ticket/receipt drafts for `shape_intake` |
| `acceptance_config_helpers.py` | — | Minimal registry bundle tree for config/archive workspaces |
| `acceptance_catalog_helpers.py` | — | Catalog index path resolution (output dir vs default docs path) |
| `steps/execute_workspace.py` | `acceptance_flow_helpers`, `stub_execute_env` | Execute manifest/git and stub-env Given steps |
| `deliver_stub_handoff_helpers.py` | `implementation_flow_helpers` | Full-path arrange/assert for `deliver.stub` handoff |
| `test_deliver_stub_handoff.py` | `deliver_stub_handoff_helpers`, `stub_execute_env` | Pytest mirror of deliver handoff (no `.feature` yet) |

**CLI invocation:** steps call `acceptance_invoke.invoke_acceptance_command`; argv assembly stays in `helpers.invoke_foundry`. Unit tests use `implementation_flow_helpers.invoke_foundry_cli`.

**Step modules stay thin:** scenario-specific `@when`/`@then` only; arrange/act helpers live in support modules above.
