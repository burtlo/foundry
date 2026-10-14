# `app discover`

Status: **implemented**

Inspect the workspace repository and emit a proposed `.foundry/app.yaml` manifest draft without writing files. First step of app bootstrap (`app discover`).

## Invocation

```bash
foundry app discover [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

_No command-specific flags._

## Acceptance

[app_bootstrap.feature](../../.cursor/foundry/cli/tests/acceptance/features/app_bootstrap.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
