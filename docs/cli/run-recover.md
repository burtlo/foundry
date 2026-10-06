# `run recover`

Status: **implemented**

Reload snapshot and advance (crash-safe resume).

## Invocation

```bash
foundry run recover [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--flow` | no | — | Flow id override |
| `--step-budget` | no | 8 | — |

## Acceptance

[job_host.feature](../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
