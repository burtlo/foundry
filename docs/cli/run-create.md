# `run create`

Status: **implemented**

Create a new run, admit the flow entry visit, and run engine admission hooks.

## Invocation

```bash
foundry run create [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--flow` | no | — | Flow id (default: implementation) |
| `--run-id` | no | — | Explicit run id slug |

## Acceptance

[shape_intake.feature](../../.cursor/foundry/cli/tests/acceptance/features/shape_intake.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
