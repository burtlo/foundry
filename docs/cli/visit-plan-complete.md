# `visit plan complete`

Status: **implemented**

Publish execution graph and brief after accepted plan judgment.

## Invocation

```bash
foundry visit plan complete [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--summary` | no | — | Short summary for visit transition on success |
| `--revision` | no | — | Expected snapshot revision before commit |

## Acceptance

[execute_plan.feature](../../.cursor/foundry/cli/tests/acceptance/features/execute_plan.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
