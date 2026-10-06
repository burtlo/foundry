# `run advance`

Status: **implemented**

Bounded durable advancement until wait or step budget.

## Invocation

```bash
foundry run advance [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--flow` | no | — | Flow id override |
| `--revision` | no | — | Expected snapshot revision; returns STALE_REVISION on conflict |
| `--step-budget` | no | 8 | Maximum automatic steps per invocation (default: 8) |
| `--local` | no | false | Advance on disk even when the job host is running |

## Acceptance

[job_host.feature](../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
