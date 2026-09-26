# `dev acceptance`

Status: **implemented**

Run the Foundry CLI Gherkin acceptance suite (pytest tests/acceptance).

## Invocation

```bash
foundry dev acceptance [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--quiet` | no | false | Reduce pytest verbosity |
| `--include-dev-scenarios` | no | false | Also run dev_commands.feature (meta-testing only; may recurse if misused) |
| `pytest_args` | no | — | Extra arguments passed to pytest |

## Acceptance

[dev_commands.feature](../../.cursor/foundry/cli/tests/acceptance/features/dev_commands.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
