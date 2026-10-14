# `decide`

Status: **implemented**

Submit a user gate decision when wait.kind is decision.

## Invocation

```bash
foundry decide [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `run` | yes | — | Run id |
| `option` | yes | — | One of the gate option values |
| `--revision` | no | — | Expected snapshot revision; returns STALE_REVISION on conflict |
| `--local` | no | false | Decide on disk even when the job host is running |

## Acceptance

[user_cli.feature](../../.cursor/foundry/cli/tests/acceptance/features/user_cli.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
