# `app validate`

Status: **implemented**

Validate `.foundry/app.yaml` against `app-manifest.schema.json`. Read-only probe used by the `validate-manifest` catalog check.

## Invocation

```bash
foundry app validate [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--manifest` | no | — | Explicit manifest path (default: workspace .foundry/app.yaml) |

## Acceptance

[app_bootstrap.feature](../../.cursor/foundry/cli/tests/acceptance/features/app_bootstrap.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
