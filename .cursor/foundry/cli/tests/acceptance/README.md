# Foundry CLI acceptance tests

Gherkin behavioral contracts for the v1 CLI slice. Features live here; step definitions live in `steps/`.

## Features

| Feature | Command under test |
|---|---|
| `run_context.feature` | `foundry run context` (`--json` schema validation; `--markdown` steward packet) |
| `catalog_build.feature` | `foundry catalog build` |
| `doc_build.feature` | `foundry doc build` (node and CLI self-docs) |
| `dev_commands.feature` | `foundry dev docs`, `dev unit`, `dev acceptance`, `dev all` |

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

Workflow concepts live in `docs/concepts/`. CLI reference pages under `docs/cli/` are generated as commands ship (`foundry dev docs`)
