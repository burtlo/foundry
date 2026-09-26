# Foundry CLI (v1 slice)

Python CLI for the v1 workflow engine.

## Setup

```bash
cd .cursor/foundry/cli
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Developer shortcuts

From the repository root:

```bash
CLI=.cursor/foundry/cli/.venv/bin/python
ENTRY=.cursor/foundry/cli/foundry.py

$CLI $ENTRY --workspace . dev docs
$CLI $ENTRY --workspace . dev unit
$CLI $ENTRY --workspace . dev acceptance
$CLI $ENTRY --workspace . dev all
```

From this directory:

```bash
./foundry.sh --workspace ../../.. dev all
./run_acceptance.sh
```

## Layout

```text
foundry_cli/          ← importable library
foundry.py            ← CLI entry point
tests/
  unit/
  acceptance/
    features/         ← Gherkin source of truth
    steps/
run_acceptance.sh     ← alias for dev acceptance
```

See [tests/acceptance/README.md](tests/acceptance/README.md).

## Runtime example

```bash
./foundry.sh --workspace ../../.. run context --markdown \
  --run-dir ../fixtures/runs/porcelain-0007-v001
```

Use `--json` for the context-packet envelope (schema validation, acceptance tests).
