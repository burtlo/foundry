# `status`

Status: **implemented**

Show run snapshot summary; default run when exactly one active run.

## Invocation

```bash
foundry status [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `run` | no | — | Run id (optional when unambiguous) |
| `--local` | no | false | Read from disk even when the job host is running |

## Acceptance

[user_cli.feature](../../.cursor/foundry/cli/tests/acceptance/features/user_cli.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
