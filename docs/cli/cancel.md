# `cancel`

Status: **implemented**

Halt a non-terminal run with a required --reason recorded in the ledger.

## Invocation

```bash
foundry cancel [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `run` | yes | — | Run id |
| `--reason` | yes | — | Why the run is being cancelled |
| `--revision` | no | — | Expected snapshot revision |
| `--local` | no | false | Cancel on disk even when the job host is running |

## Acceptance

[user_cli.feature](../../.cursor/foundry/cli/tests/acceptance/features/user_cli.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
