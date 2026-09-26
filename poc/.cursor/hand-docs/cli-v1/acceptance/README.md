# CLI v1 — acceptance specifications

Behavioral contracts for the Foundry CLI. These Gherkin features are the **source of truth** for what each command must do. Implementation in `.cursor/foundry/cli/` is judged by whether it passes this suite.

## Layout

```text
docs/cli-v1/acceptance/
  README.md                 ← this file
  features/
    run_context.feature     ← steward context command
    catalog_build.feature   ← node index generation
    doc_build.feature       ← documentation generation
    dev_commands.feature    ← dev docs / unit / acceptance shortcuts

.cursor/foundry/cli/
  foundry_cli/              ← implementation package
  tests/
    unit/                   ← unit tests (e.g. test_paths.py)
    acceptance/
      helpers.py            ← subprocess runner, shared assertion helpers
      steps/
      test_*.py             ← scenario registration
  run_acceptance.sh         ← wrapper → foundry dev acceptance
```

Fixtures referenced by scenarios live under `.cursor/foundry/fixtures/`.

Structural validation uses JSON Schemas in `.cursor/foundry/schemas/` (shape only; scenarios define meaning).

## Implemented commands

| Command | Feature | Schema | Runner |
|---|---|---|---|
| `foundry run context` | [run_context.feature](features/run_context.feature) | [context-packet.schema.json](../../../.cursor/foundry/schemas/context-packet.schema.json) | `foundry dev acceptance` |
| `foundry catalog build` | [catalog_build.feature](features/catalog_build.feature) | — | `foundry dev acceptance` |
| `foundry doc build` | [doc_build.feature](features/doc_build.feature) | — | `foundry dev acceptance` |
| `foundry dev docs` | [dev_commands.feature](features/dev_commands.feature) | — | `foundry dev acceptance` |
| `foundry dev unit` | [dev_commands.feature](features/dev_commands.feature) | — | `foundry dev unit` |
| `foundry dev acceptance` | [dev_commands.feature](features/dev_commands.feature) | — | `foundry dev acceptance` |
| `foundry dev all` | [dev_commands.feature](features/dev_commands.feature) | — | `foundry dev all` |

Developer shortcut spec: [cli-dev.md](../cli-dev.md).

## Run the suite

From the repository root:

```bash
cd .cursor/foundry/cli
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python foundry.py --workspace ../.. dev all
```

Individual shortcuts:

```bash
.venv/bin/python foundry.py --workspace ../.. dev unit
.venv/bin/python foundry.py --workspace ../.. dev acceptance
.venv/bin/python foundry.py --workspace ../.. dev docs
```

Filter scenarios:

```bash
.venv/bin/python foundry.py --workspace ../.. dev acceptance -k run_context
```

## pytest-bdd vs behave

This repo uses **pytest-bdd** (features in `docs/`, steps in `.cursor/foundry/cli/tests/acceptance/steps/`).

Keep a single Gherkin source under `docs/cli-v1/acceptance/features/` and point either runner at it.

## Adding a command

1. Add `features/<command>.feature` with Given/When/Then scenarios and fixture references.
2. Add `tests/acceptance/steps/<command>.py` with `@given` / `@when` / `@then` bindings.
3. Add `tests/acceptance/test_<command>.py` that calls `scenarios("<command>.feature")`.
4. Register the step module in `tests/conftest.py` `pytest_plugins`.
5. Register any new fixtures under `.cursor/foundry/fixtures/`.
6. Add a row to the **Implemented commands** table above when scenarios pass.
