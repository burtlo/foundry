# `dev unit`

Status: **implemented**

Run the Foundry CLI unit test suite (pytest tests/unit).

## Invocation

```bash
foundry dev unit [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--quiet` | no | false | Reduce pytest verbosity |
| `--parallel` | no | false | Run with pytest-xdist (`-n auto`); skipped if `pytest_args` already passes `-n` |
| `pytest_args` | no | — | Extra arguments passed to pytest (e.g. `-k hooks`, `-m node.shape.intake`) |

## Acceptance

[dev_commands.feature](../../.cursor/foundry/cli/tests/acceptance/features/dev_commands.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
