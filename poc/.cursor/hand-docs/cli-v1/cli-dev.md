# Foundry CLI — developer shortcuts (`dev`)

Status: **implemented**

Developer workflow aliases that wrap the importable Python library in `foundry_cli/dev.py`.

## Commands

| Command | Alias for | Purpose |
|---|---|---|
| `foundry dev docs` | `build_catalog` + `write_generated_docs` | Regenerate catalog indexes and `docs/generated/` |
| `foundry dev unit` | `pytest tests/unit` | Fast unit tests |
| `foundry dev acceptance` | `pytest tests/acceptance` | Gherkin integration tests |
| `foundry dev all` | unit then acceptance | Full local check before merge |

## Usage

From the repository root (preferred):

```bash
.cursor/foundry/cli/.venv/bin/python .cursor/foundry/cli/foundry.py \
  --workspace . dev docs

.cursor/foundry/cli/.venv/bin/python .cursor/foundry/cli/foundry.py \
  --workspace . dev unit

.cursor/foundry/cli/.venv/bin/python .cursor/foundry/cli/foundry.py \
  --workspace . dev acceptance

.cursor/foundry/cli/.venv/bin/python .cursor/foundry/cli/foundry.py \
  --workspace . dev all
```

From `.cursor/foundry/cli` (with venv activated):

```bash
./foundry.sh --workspace ../.. dev all
./run_acceptance.sh          # same as dev acceptance
```

## Flags

| Flag | Commands | Meaning |
|---|---|---|
| `--json` | all | Emit structured JSON envelope (global flag) |
| `--quiet` | unit, acceptance, all | Reduce pytest verbosity |
| `--smoke` | docs | Generate `shape.intake` only (fast; skips full index) |
| `--include-dev-scenarios` | acceptance, all | Include `dev_commands.feature` (meta-testing; default excludes it) |
| `--flow` | docs | Flow id (default: `implementation`) |
| `--output` | docs | Output directory (default: `docs/generated`) |

Extra pytest arguments may follow unit/acceptance/all commands:

```bash
foundry dev unit -k test_paths
foundry dev acceptance -k run_context
```

## Library API

```python
from foundry_cli.dev import run_dev_docs, run_unit_tests, run_acceptance_tests, run_all_tests
```

## Acceptance spec

Behavior is defined in [dev_commands.feature](../acceptance/features/dev_commands.feature).

## Related

- [cli-run.md](cli-run.md) — steward runtime commands
- [cli-registry.md](cli-registry.md) — `catalog build`, `doc build`
- [acceptance/README.md](../acceptance/README.md) — full BDD layout
