# Foundry

Cursor plugin and workflow engine for shaping, executing, and verifying feature work. The **implementation** flow is declared in `factory-flow.yaml` and driven by the Foundry Python CLI and local job host.

**Documentation:** [docs/index.md](docs/index.md) — workflow [concepts](docs/concepts/README.md) (hand-maintained) plus generated flow, node, and CLI pages (`foundry dev docs`).

---

## Layout

| Path | Role |
|---|---|
| `.cursor/foundry/flows/factory-flow.yaml` | Flow graph (nodes, checks, connections) |
| `.cursor/foundry/nodes/` | Steward instructions per node |
| `.cursor/foundry/workers/` | Worker capability contracts |
| `.cursor/agents/` | Meta subagents (`scribe`, `scribe-verifier`, `run-evaluator`) |
| `.cursor/foundry/cli/` | Python CLI, library, and tests |
| `.cursor/foundry/cli/tests/acceptance/features/` | Gherkin acceptance contracts |
| `docs/` | Generated reference from `factory-flow.yaml` (`foundry dev docs`) plus hand-maintained `concepts/` |
| `docs/concepts/` | Workflow model — graph, lifecycle, artifacts, control plane (hand-maintained) |

---

## Setup

```bash
cd .cursor/foundry/cli
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## Developer CLI

Single entry point for local workflow (`foundry_cli/dev.py`).

### From the repository root

```bash
CLI=.cursor/foundry/cli/.venv/bin/python
ENTRY=.cursor/foundry/cli/foundry.py

$CLI $ENTRY --workspace . dev docs        # catalog indexes + docs/
$CLI $ENTRY --workspace . dev unit        # pytest tests/unit
$CLI $ENTRY --workspace . dev acceptance  # pytest tests/acceptance (Gherkin)
$CLI $ENTRY --workspace . dev all         # unit, then acceptance
```

### From `.cursor/foundry/cli`

```bash
./foundry.sh --workspace ../../.. dev all
./run_acceptance.sh                       # alias for dev acceptance
```

### Useful flags

| Flag | Commands | Purpose |
|---|---|---|
| `--quiet` | `dev unit`, `dev acceptance`, `dev all` | Less pytest output |
| `--smoke` | `dev docs` | Generate `shape.intake` only (fast check) |
| `--json` | any | Structured JSON response envelope |
| `--include-dev-scenarios` | `dev acceptance`, `dev all` | Include `dev_commands.feature` (meta-testing; excluded by default) |

### Python library

```python
from foundry_cli.dev import run_dev_docs, run_unit_tests, run_acceptance_tests, run_all_tests
```

---

## Tests

```bash
cd .cursor/foundry/cli
.venv/bin/python foundry.py --workspace ../../.. dev all
```

Gherkin features: `.cursor/foundry/cli/tests/acceptance/features/`

**Note:** `dev acceptance` and `dev all` exclude `dev_commands.feature` by default to avoid nested subprocess runs.

---

## Runtime example

```bash
cd .cursor/foundry/cli
./foundry.sh --workspace ../../.. run context --markdown \
  --run-dir ../fixtures/runs/porcelain-0007-v001
```

Use `--json` instead of `--markdown` for schema validation and programmatic use.

More detail: [.cursor/foundry/cli/README.md](.cursor/foundry/cli/README.md).
