# `start`

Status: **implemented**

Explicit Shape → Execute authorization at execute.start; records execute.authorization.recorded and advances into execute.intake.

## Invocation

```bash
foundry start [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `run` | no | — | Run id (optional when unambiguous) |
| `--revision` | no | — | Expected snapshot revision; returns STALE_REVISION on conflict |
| `--no-host` | no | false | Do not auto-start the job host |
| `--local` | no | false | Authorize and advance on disk even when the job host is running |

## Acceptance

[user_cli.feature](../../.cursor/foundry/cli/tests/acceptance/features/user_cli.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
